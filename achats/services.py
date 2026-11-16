from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from rapports.models import JournalAudit
from stock.models import LotStock, MouvementStock

from .models import CommandeAchat, LigneReception


TRANSITIONS_AUTORISEES = {
    CommandeAchat.Statut.BROUILLON: {CommandeAchat.Statut.COMMANDEE, CommandeAchat.Statut.ANNULEE},
    CommandeAchat.Statut.COMMANDEE: {
        CommandeAchat.Statut.PARTIELLEMENT_RECEPTIONNEE,
        CommandeAchat.Statut.ENTIEREMENT_RECEPTIONNEE,
        CommandeAchat.Statut.ANNULEE,
    },
    CommandeAchat.Statut.PARTIELLEMENT_RECEPTIONNEE: {
        CommandeAchat.Statut.PARTIELLEMENT_RECEPTIONNEE,
        CommandeAchat.Statut.ENTIEREMENT_RECEPTIONNEE,
        CommandeAchat.Statut.ANNULEE,
    },
    CommandeAchat.Statut.ENTIEREMENT_RECEPTIONNEE: set(),
    CommandeAchat.Statut.ANNULEE: set(),
}


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


def changer_statut(commande, nouveau_statut, request=None, utilisateur=None, description=""):
    utilisateur = utilisateur or getattr(request, "user", None)
    with transaction.atomic():
        commande = (
            CommandeAchat.objects.select_for_update()
            .select_related("fournisseur")
            .get(pk=commande.pk)
        )
        autorises = TRANSITIONS_AUTORISEES.get(commande.statut, set())
        if nouveau_statut not in autorises:
            raise ValidationError(
                f"Transition de statut interdite : {commande.get_statut_display()} → "
                f"{CommandeAchat.Statut(nouveau_statut).label}."
            )
        if nouveau_statut == CommandeAchat.Statut.COMMANDEE and not commande.lignes.exists():
            raise ValidationError("Impossible de valider une commande sans ligne.")
        commande.statut = nouveau_statut
        commande.save(update_fields=["statut", "date_modification"])
        journaliser(
            request,
            utilisateur,
            JournalAudit.Action.VALIDATION if nouveau_statut == CommandeAchat.Statut.COMMANDEE else JournalAudit.Action.ANNULATION,
            commande,
            description or f"Statut changé vers {commande.get_statut_display()}.",
        )
        return commande


def calculer_statut_reception(commande):
    lignes = list(commande.lignes.all())
    if not lignes:
        return commande.statut
    toutes_recues = all(ligne.quantite_restante == 0 for ligne in lignes)
    if toutes_recues:
        return CommandeAchat.Statut.ENTIEREMENT_RECEPTIONNEE
    if any(ligne.quantite_recue > 0 for ligne in lignes):
        return CommandeAchat.Statut.PARTIELLEMENT_RECEPTIONNEE
    return CommandeAchat.Statut.COMMANDEE


def valider_reception(reception, lignes_data, request=None, utilisateur=None):
    """Valide une réception (création+validation) dans une transaction atomique.

    lignes_data: iterable de dicts {ligne_achat, quantite, numero_lot, date_peremption}
    RG04: ne modifie le stock qu'ici (réception validée). RG05: verrouillage anti double validation.
    """
    utilisateur = utilisateur or getattr(request, "user", None)
    with transaction.atomic():
        reception = (
            type(reception)
            .objects.select_for_update()
            .select_related("commande", "commande__fournisseur")
            .get(pk=reception.pk)
        )
        if reception.est_validee:
            raise ValidationError("Cette réception a déjà été validée.")

        commande = CommandeAchat.objects.select_for_update().get(pk=reception.commande_id)
        if commande.statut not in {
            CommandeAchat.Statut.COMMANDEE,
            CommandeAchat.Statut.PARTIELLEMENT_RECEPTIONNEE,
        }:
            raise ValidationError(
                "La réception n'est possible que pour une commande commandée ou partiellement réceptionnée."
            )

        lignes_recues = [
            d for d in lignes_data
            if (d.get("quantite") or 0) > 0
        ]
        if not lignes_recues:
            raise ValidationError("Saisissez au moins une ligne à réceptionner.")

        lignes_commande = {
            l.pk: l
            for l in commande.lignes.select_for_update().select_related("medicament")
        }

        for data in lignes_recues:
            ligne_achat = lignes_commande.get(getattr(data["ligne_achat"], "pk", data["ligne_achat"]))
            if not ligne_achat:
                raise ValidationError("Ligne de commande invalide pour cette commande.")
            if data["quantite"] > ligne_achat.quantite_restante:
                raise ValidationError(
                    f"Quantité reçue supérieure au restant pour « {ligne_achat.medicament} »."
                )
            if data["date_peremption"] < timezone.localdate():
                raise ValidationError("La date de péremption ne peut pas être dans le passé.")

            lot, cree = LotStock.objects.select_for_update().get_or_create(
                medicament=ligne_achat.medicament,
                numero_lot=data["numero_lot"].strip(),
                defaults={
                    "date_peremption": data["date_peremption"],
                    "quantite_recue": 0,
                    "quantite_disponible": 0,
                    "bloque": False,
                },
            )
            if not cree and lot.date_peremption != data["date_peremption"]:
                raise ValidationError(
                    f"Le lot {lot.numero_lot} existe déjà pour ce médicament avec une autre date de péremption."
                )

            LigneReception.objects.create(
                reception=reception,
                ligne_achat=ligne_achat,
                quantite=data["quantite"],
                numero_lot=lot.numero_lot,
                date_peremption=lot.date_peremption,
                lot=lot,
            )

            LotStock.objects.filter(pk=lot.pk).update(
                quantite_recue=F("quantite_recue") + data["quantite"],
                quantite_disponible=F("quantite_disponible") + data["quantite"],
            )
            lot.refresh_from_db(fields=["quantite_recue", "quantite_disponible"])

            MouvementStock.objects.create(
                type_mouvement=MouvementStock.TypeMouvement.ENTREE,
                quantite=data["quantite"],
                lot=lot,
                auteur=utilisateur,
                reference=reception.numero,
                commentaire=f"Réception {reception.numero} / commande {commande.numero}",
            )

        reception.est_validee = True
        reception.date_validation = timezone.now()
        reception.validee_par = utilisateur
        reception.save(update_fields=["est_validee", "date_validation", "validee_par"])

        nouveau_statut = calculer_statut_reception(commande)
        if nouveau_statut != commande.statut:
            commande.statut = nouveau_statut
            commande.save(update_fields=["statut", "date_modification"])

        journaliser(
            request,
            utilisateur,
            JournalAudit.Action.VALIDATION,
            reception,
            f"Réception validée pour la commande {commande.numero}.",
        )
        journaliser(
            request,
            utilisateur,
            JournalAudit.Action.MODIFICATION,
            commande,
            f"Commande mise à jour après réception ({commande.get_statut_display()}).",
        )
        return reception
