from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

from medicaments.models import Medicament
from rapports.models import JournalAudit
from utilisateurs.roles import PHARMACIEN_RESPONSABLE

from .models import LotStock, MouvementStock

DEFAULT_JOURS_ALERTE_PEREMPTION = 30


def _ip_client(request):
    if not request:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def journaliser(request, utilisateur, action, instance, description=""):
    JournalAudit.objects.create(
        utilisateur=utilisateur,
        action=action,
        modele=instance.__class__.__name__,
        objet_id=str(instance.pk),
        description=description,
        adresse_ip=_ip_client(request),
    )


def est_pharmacien_responsable(user):
    return bool(user and (user.is_superuser or user.a_un_role(PHARMACIEN_RESPONSABLE)))


def get_lots_fefo(medicament):
    """Lots non périmés, non bloqués, quantité > 0, triés par péremption croissante."""
    aujourd_hui = timezone.localdate()
    qs = LotStock.objects.filter(quantite_disponible__gt=0, bloque=False)
    if isinstance(medicament, Medicament):
        qs = qs.filter(medicament=medicament)
    elif medicament is not None:
        qs = qs.filter(medicament_id=medicament)
    return qs.filter(date_peremption__gte=aujourd_hui).order_by(
        "date_peremption", "date_reception", "pk"
    )


def stock_valide_medicament(medicament_id):
    """Somme des quantités disponibles des lots valides (non périmés, non bloqués)."""
    aujourd_hui = timezone.localdate()
    return (
        LotStock.objects.filter(
            medicament_id=medicament_id,
            bloque=False,
            date_peremption__gte=aujourd_hui,
            quantite_disponible__gt=0,
        ).aggregate(total=Sum("quantite_disponible"))["total"]
        or 0
    )


def calculer_alertes(jours_peremption=DEFAULT_JOURS_ALERTE_PEREMPTION):
    """Retourne les alertes stock: ruptures, sous seuil, périmés, péremption proche."""
    aujourd_hui = timezone.localdate()
    limite = aujourd_hui + timedelta(days=jours_peremption)

    medicaments = Medicament.objects.filter(statut=Medicament.Statut.ACTIF).annotate(
        stock_valide=Sum(
            "lots__quantite_disponible",
            filter=Q(
                lots__bloque=False,
                lots__date_peremption__gte=aujourd_hui,
                lots__quantite_disponible__gt=0,
            ),
        )
    )
    ruptures = []
    sous_seuil = []
    for med in medicaments:
        stock = med.stock_valide or 0
        med.stock_valide_calc = stock
        if stock <= 0:
            ruptures.append(med)
        elif stock < med.seuil_alerte:
            sous_seuil.append(med)

    lots_perimes = (
        LotStock.objects.select_related("medicament")
        .filter(date_peremption__lt=aujourd_hui, quantite_disponible__gt=0)
        .order_by("date_peremption")
    )
    lots_proches = (
        LotStock.objects.select_related("medicament")
        .filter(
            date_peremption__gte=aujourd_hui,
            date_peremption__lte=limite,
            quantite_disponible__gt=0,
            bloque=False,
        )
        .order_by("date_peremption")
    )
    return {
        "ruptures": ruptures,
        "sous_seuil": sous_seuil,
        "lots_perimes": lots_perimes,
        "lots_proches": lots_proches,
        "jours_peremption": jours_peremption,
    }


@transaction.atomic
def appliquer_correction_inventaire(lot, stock_compte, motif, utilisateur, request=None):
    if not motif or not str(motif).strip():
        raise ValidationError("Le motif de la correction est obligatoire.")
    if stock_compte is None or stock_compte < 0:
        raise ValidationError("Le stock compté doit être un entier positif ou nul.")

    lot = LotStock.objects.select_for_update().select_related("medicament").get(pk=lot.pk)
    ancien_disponible = lot.quantite_disponible
    ancien_recu = lot.quantite_recue
    ecart = stock_compte - ancien_disponible

    if ecart == 0:
        raise ValidationError("Aucun écart : le stock compté est identique au stock disponible.")

    if ecart < 0:
        # retrait
        lot.quantite_disponible = stock_compte
    else:
        # ajout : on augmente aussi la quantité reçue pour respecter la contrainte <= reçue
        lot.quantite_disponible = stock_compte
        if lot.quantite_disponible > lot.quantite_recue:
            lot.quantite_recue = lot.quantite_disponible

    lot.save(update_fields=["quantite_disponible", "quantite_recue"])

    sens = "ajustement +" if ecart > 0 else "ajustement -"
    mouvement = MouvementStock.objects.create(
        type_mouvement=MouvementStock.TypeMouvement.CORRECTION,
        quantite=abs(ecart),
        lot=lot,
        auteur=utilisateur,
        reference=f"INV-LOT-{lot.pk}",
        commentaire=(
            f"Inventaire: compté={stock_compte}, disponible_avant={ancien_disponible}, "
            f"écart={ecart} ({sens}). Motif: {str(motif).strip()}"
        ),
    )
    journaliser(
        request,
        utilisateur,
        JournalAudit.Action.MODIFICATION,
        lot,
        f"Correction inventaire lot {lot.numero_lot} ({lot.medicament}) : écart {ecart}. Motif: {str(motif).strip()}",
    )
    return mouvement, ecart


def _verifier_pharmacien(user):
    if not est_pharmacien_responsable(user):
        raise PermissionDenied("Action réservée au pharmacien responsable.")


@transaction.atomic
def changer_blocage_lot(lot, bloque, utilisateur, request=None):
    _verifier_pharmacien(utilisateur)
    lot = LotStock.objects.select_for_update().select_related("medicament").get(pk=lot.pk)
    if lot.bloque == bloque:
        raise ValidationError("Le lot est déjà dans cet état.")
    lot.bloque = bloque
    lot.save(update_fields=["bloque"])
    action_txt = "bloqué" if bloque else "débloqué"
    journaliser(
        request,
        utilisateur,
        JournalAudit.Action.MODIFICATION,
        lot,
        f"Lot {lot.numero_lot} ({lot.medicament}) {action_txt}.",
    )
    return lot
