import json
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from rapports.models import JournalAudit
from stock.models import LotStock, MouvementStock
from stock.services import get_lots_fefo
from utilisateurs.roles import ADMINISTRATEUR, PHARMACIEN_RESPONSABLE

from .models import LigneVente, Paiement, RetourVente, Vente


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


def _verifier_permission_retour(user):
    if not user or not (
        user.is_superuser or user.a_un_role(PHARMACIEN_RESPONSABLE, ADMINISTRATEUR)
    ):
        raise PermissionDenied(
            "Action réservée au pharmacien responsable ou à l'administrateur."
        )


def lots_valides_pour(medicament):
    return get_lots_fefo(medicament).select_related("medicament")


def _parse_lignes_payload(payload):
    if not payload:
        raise ValidationError("Le panier est vide.")
    try:
        data = json.loads(payload)
    except (TypeError, ValueError):
        raise ValidationError("Données du panier invalides.")
    if not isinstance(data, list) or not data:
        raise ValidationError("Ajoutez au moins un médicament au panier.")

    lignes = []
    for idx, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValidationError(f"Ligne {idx} invalide.")
        try:
            lot_id = int(item.get("lot_id"))
            quantite = int(item.get("quantite"))
        except (TypeError, ValueError):
            raise ValidationError(f"Ligne {idx} : lot ou quantité invalide.")
        if quantite <= 0:
            raise ValidationError(f"Ligne {idx} : la quantité doit être strictement positive (RG06).")
        lignes.append({"lot_id": lot_id, "quantite": quantite})
    return lignes


@transaction.atomic
def confirmer_vente(*, lignes_payload, mode_paiement, client=None, commentaire="", utilisateur, request=None):
    """Crée et valide une vente atomiquement avec verrouillage des lots (RG06/RG07/RG08/RG12)."""
    lignes_data = _parse_lignes_payload(lignes_payload)
    if mode_paiement not in Paiement.Mode.values:
        raise ValidationError("Mode de paiement invalide.")

    # Regrouper quantités par lot pour vérifier le cumul
    demandes = {}
    ordre = []
    for item in lignes_data:
        lid = item["lot_id"]
        if lid not in demandes:
            demandes[lid] = 0
            ordre.append(lid)
        demandes[lid] += item["quantite"]

    # Verrouiller les lots concernés de manière déterministe (anti deadlock)
    lot_ids = sorted(demandes.keys())
    lots = list(
        LotStock.objects.select_for_update()
        .select_related("medicament")
        .filter(pk__in=lot_ids)
    )
    lots_map = {lot.pk: lot for lot in lots}
    if len(lots_map) != len(lot_ids):
        raise ValidationError("Un des lots sélectionnés est introuvable.")

    aujourd_hui = timezone.localdate()

    # Re-vérifications serveur (RG06, RG07, RG08)
    for lot_id in lot_ids:
        lot = lots_map[lot_id]
        qte = demandes[lot_id]
        if qte <= 0:
            raise ValidationError("La quantité doit être strictement positive (RG06).")
        if lot.bloque:
            raise ValidationError(f"Le lot {lot.numero_lot} ({lot.medicament}) est bloqué (RG07).")
        if lot.date_peremption < aujourd_hui:
            raise ValidationError(f"Le lot {lot.numero_lot} ({lot.medicament}) est périmé (RG07).")
        if qte > lot.quantite_disponible:
            raise ValidationError(
                f"Stock insuffisant pour {lot.medicament} (lot {lot.numero_lot}) : "
                f"demandé {qte}, disponible {lot.quantite_disponible} (RG06/RG08)."
            )

    vente = Vente.objects.create(
        client=client,
        statut=Vente.Statut.BROUILLON,
        auteur=utilisateur,
        commentaire=commentaire or "",
    )

    montant_total = Decimal("0.00")
    for lot_id in lot_ids:
        lot = lots_map[lot_id]
        qte = demandes[lot_id]
        prix_applique = lot.medicament.prix_vente  # figé (RG12)
        if prix_applique is None or prix_applique < 0:
            raise ValidationError(f"Prix de vente invalide pour {lot.medicament}.")
        LigneVente.objects.create(
            vente=vente,
            lot=lot,
            quantite=qte,
            prix_applique=prix_applique,
        )
        # décrément atomique + garde-fou stock jamais négatif
        updated = LotStock.objects.filter(
            pk=lot.pk, quantite_disponible__gte=qte
        ).update(quantite_disponible=F("quantite_disponible") - qte)
        if updated != 1:
            raise ValidationError(
                f"Stock insuffisant pour {lot.medicament} (lot {lot.numero_lot}) (RG08)."
            )
        MouvementStock.objects.create(
            type_mouvement=MouvementStock.TypeMouvement.SORTIE,
            quantite=qte,
            lot=lot,
            auteur=utilisateur,
            reference=vente.numero,
            commentaire=f"Vente {vente.numero}",
        )
        montant_total += prix_applique * qte

    statut_paiement = (
        Paiement.Statut.EN_ATTENTE
        if mode_paiement == Paiement.Mode.MOBILE_MONEY
        else Paiement.Statut.VALIDE
    )
    Paiement.objects.create(
        vente=vente,
        mode=mode_paiement,
        statut=statut_paiement,
        montant=montant_total,
        auteur=utilisateur,
    )

    vente.statut = Vente.Statut.VALIDEE
    vente.date_validation = timezone.now()
    vente.save(update_fields=["statut", "date_validation"])

    journaliser(
        request,
        utilisateur,
        JournalAudit.Action.VALIDATION,
        vente,
        f"Vente validǸe ({montant_total}). Paiement: {mode_paiement} ({statut_paiement}).",
    )
    return vente


@transaction.atomic
def enregistrer_retour_ligne(*, ligne_vente, quantite, motif, reintegrable, utilisateur, request=None):
    _verifier_permission_retour(utilisateur)
    if not motif or not str(motif).strip():
        raise ValidationError("Le motif du retour est obligatoire.")

    ligne = (
        LigneVente.objects.select_for_update()
        .select_related("vente", "lot", "lot__medicament")
        .get(pk=ligne_vente.pk if hasattr(ligne_vente, "pk") else ligne_vente)
    )
    vente = Vente.objects.select_for_update().get(pk=ligne.vente_id)
    if vente.statut != Vente.Statut.VALIDEE:
        raise ValidationError("Seule une vente validée peut faire l'objet d'un retour.")
    if quantite is None or int(quantite) <= 0:
        raise ValidationError("La quantité retournée doit être strictement positive.")

    quantite = int(quantite)
    deja_retournee = ligne.retours.aggregate(total=Sum("quantite"))["total"] or 0
    retournable = ligne.quantite - deja_retournee
    if quantite > retournable:
        raise ValidationError(
            f"Quantité retournée ({quantite}) supérieure à la quantité retournable ({retournable})."
        )

    lot = LotStock.objects.select_for_update().get(pk=ligne.lot_id)
    mouvement = None
    if reintegrable:
        lot.quantite_disponible = F("quantite_disponible") + quantite
        lot.save(update_fields=["quantite_disponible"])
        lot.refresh_from_db(fields=["quantite_disponible"])
        mouvement = MouvementStock.objects.create(
            type_mouvement=MouvementStock.TypeMouvement.RETOUR,
            quantite=quantite,
            lot=lot,
            auteur=utilisateur,
            reference=vente.numero,
            commentaire=f"Retour vente {vente.numero} - {str(motif).strip()}",
        )

    montant = ligne.prix_applique * quantite
    retour = RetourVente.objects.create(
        vente=vente,
        ligne_vente=ligne,
        lot=lot,
        quantite=quantite,
        reintegrable=bool(reintegrable),
        type_retour=RetourVente.TypeRetour.RETOUR_LIGNE,
        montant=montant,
        motif=str(motif).strip(),
        auteur=utilisateur,
    )
    journaliser(
        request,
        utilisateur,
        JournalAudit.Action.MODIFICATION,
        vente,
        f"Retour ligne {ligne.pk} (lot {lot.numero_lot}) qté={quantite}, réintégrable={bool(reintegrable)}, montant={montant}. Motif: {str(motif).strip()}",
    )
    if mouvement:
        journaliser(request, utilisateur, JournalAudit.Action.MODIFICATION, mouvement, f"Mouvement de retour pour {vente.numero}.")
    return retour


@transaction.atomic
def annuler_vente(*, vente, motif, utilisateur, request=None):
    _verifier_permission_retour(utilisateur)
    if not motif or not str(motif).strip():
        raise ValidationError("Le motif de l'annulation est obligatoire.")

    vente = (
        Vente.objects.select_for_update()
        .prefetch_related("lignes__lot", "lignes__retours")
        .get(pk=vente.pk if hasattr(vente, "pk") else vente)
    )
    if vente.statut != Vente.Statut.VALIDEE:
        raise ValidationError("Seule une vente validée peut être annulée.")

    # tous les lots de la vente (aucun retour partiel préalable pour une annulation complète)
    for ligne in vente.lignes.all():
        deja_retournee = sum(r.quantite for r in ligne.retours.all())
        if deja_retournee != 0:
            raise ValidationError("Impossible d'annuler une vente ayant déjà des retours enregistrés.")

    montant_total = Decimal("0.00")
    for ligne in vente.lignes.all():
        lot = LotStock.objects.select_for_update().get(pk=ligne.lot_id)
        lot.quantite_disponible = F("quantite_disponible") + ligne.quantite
        lot.save(update_fields=["quantite_disponible"])
        lot.refresh_from_db(fields=["quantite_disponible"])
        MouvementStock.objects.create(
            type_mouvement=MouvementStock.TypeMouvement.RETOUR,
            quantite=ligne.quantite,
            lot=lot,
            auteur=utilisateur,
            reference=vente.numero,
            commentaire=f"Annulation vente {vente.numero} - {str(motif).strip()}",
        )
        montant_ligne = ligne.prix_applique * ligne.quantite
        montant_total += montant_ligne
        RetourVente.objects.create(
            vente=vente,
            ligne_vente=ligne,
            lot=lot,
            quantite=ligne.quantite,
            reintegrable=True,
            type_retour=RetourVente.TypeRetour.ANNULATION,
            montant=montant_ligne,
            motif=str(motif).strip(),
            auteur=utilisateur,
        )

    Paiement.objects.filter(vente=vente, statut=Paiement.Statut.VALIDE).update(
        statut=Paiement.Statut.ANNULE
    )
    vente.statut = Vente.Statut.ANNULEE
    vente.save(update_fields=["statut"])

    journaliser(
        request,
        utilisateur,
        JournalAudit.Action.ANNULATION,
        vente,
        f"Vente annulée (compensation). Montant compensé={montant_total}. Motif: {str(motif).strip()}",
    )
    return vente
