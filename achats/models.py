from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

from fournisseurs.models import Fournisseur
from medicaments.models import Medicament
from stock.models import LotStock


def generer_numero_commande():
    return f"CA-{timezone.localdate():%Y%m%d}-{uuid4().hex[:6].upper()}"


def generer_numero_reception():
    return f"RC-{timezone.localdate():%Y%m%d}-{uuid4().hex[:6].upper()}"


class CommandeAchat(models.Model):
    class Statut(models.TextChoices):
        BROUILLON = "brouillon", "Brouillon"
        COMMANDEE = "commandee", "Commandée"
        PARTIELLEMENT_RECEPTIONNEE = (
            "partiellement_receptionnee",
            "Partiellement réceptionnée",
        )
        ENTIEREMENT_RECEPTIONNEE = (
            "entierement_receptionnee",
            "Entièrement réceptionnée",
        )
        ANNULEE = "annulee", "Annulée"

    numero = models.CharField(
        "numéro",
        max_length=30,
        unique=True,
        editable=False,
        default=generer_numero_commande,
    )
    fournisseur = models.ForeignKey(
        Fournisseur,
        on_delete=models.PROTECT,
        related_name="commandes",
        verbose_name="fournisseur",
    )
    statut = models.CharField(
        "statut",
        max_length=30,
        choices=Statut.choices,
        default=Statut.BROUILLON,
    )
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="commandes_achat",
        verbose_name="auteur",
        editable=False,
    )
    commentaire = models.TextField("commentaire", blank=True)
    date_creation = models.DateTimeField("date de création", auto_now_add=True)
    date_modification = models.DateTimeField("date de modification", auto_now=True)

    class Meta:
        verbose_name = "commande d'achat"
        verbose_name_plural = "commandes d'achat"
        ordering = ["-date_creation", "-pk"]
        indexes = [
            models.Index(fields=["statut"]),
            models.Index(fields=["fournisseur", "statut"]),
            models.Index(fields=["-date_creation"]),
        ]

    def __str__(self):
        return f"{self.numero} - {self.fournisseur}"

    @property
    def montant_total(self):
        return sum(
            (ligne.total_ligne for ligne in self.lignes.all()), Decimal("0.00")
        )

    @property
    def est_modifiable(self):
        return self.statut in {self.Statut.BROUILLON, self.Statut.COMMANDEE}


class LigneAchat(models.Model):
    commande = models.ForeignKey(
        CommandeAchat,
        on_delete=models.CASCADE,
        related_name="lignes",
        verbose_name="commande",
    )
    medicament = models.ForeignKey(
        Medicament,
        on_delete=models.PROTECT,
        related_name="lignes_achat",
        verbose_name="médicament",
    )
    quantite = models.PositiveIntegerField(
        "quantité", validators=[MinValueValidator(1)]
    )
    prix_unitaire = models.DecimalField(
        "prix unitaire",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        verbose_name = "ligne d'achat"
        verbose_name_plural = "lignes d'achat"
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantite__gte=0),
                name="ligneachat_quantite_positive",
            ),
            models.CheckConstraint(
                condition=Q(prix_unitaire__gte=0),
                name="ligneachat_prix_unitaire_positif",
            ),
        ]
        indexes = [
            models.Index(fields=["medicament"]),
        ]

    def __str__(self):
        return f"{self.medicament} x {self.quantite}"

    @property
    def total_ligne(self):
        return self.prix_unitaire * self.quantite

    @property
    def quantite_recue(self):
        return (
            self.lignes_reception.filter(reception__est_validee=True).aggregate(
                total=Sum("quantite")
            )["total"]
            or 0
        )

    @property
    def quantite_restante(self):
        return max(0, self.quantite - self.quantite_recue)


class ReceptionAchat(models.Model):
    numero = models.CharField(
        "numéro",
        max_length=30,
        unique=True,
        editable=False,
        default=generer_numero_reception,
    )
    commande = models.ForeignKey(
        CommandeAchat,
        on_delete=models.PROTECT,
        related_name="receptions",
        verbose_name="commande",
    )
    est_validee = models.BooleanField("réception validée", default=False)
    date_validation = models.DateTimeField("date de validation", null=True, blank=True)
    validee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="receptions_validees",
        verbose_name="validée par",
        null=True,
        blank=True,
    )
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="receptions_achat",
        verbose_name="auteur",
        editable=False,
    )
    commentaire = models.TextField("commentaire", blank=True)
    date_creation = models.DateTimeField("date de création", auto_now_add=True)

    class Meta:
        verbose_name = "réception d'achat"
        verbose_name_plural = "réceptions d'achat"
        ordering = ["-date_creation", "-pk"]
        indexes = [
            models.Index(fields=["commande", "est_validee"]),
            models.Index(fields=["-date_creation"]),
        ]

    def __str__(self):
        return f"{self.numero} - {self.commande.numero}"

    @property
    def montant_total(self):
        return sum(
            (ligne.montant_ligne for ligne in self.lignes.all()), Decimal("0.00")
        )


class LigneReception(models.Model):
    reception = models.ForeignKey(
        ReceptionAchat,
        on_delete=models.CASCADE,
        related_name="lignes",
        verbose_name="réception",
    )
    ligne_achat = models.ForeignKey(
        LigneAchat,
        on_delete=models.PROTECT,
        related_name="lignes_reception",
        verbose_name="ligne de commande",
    )
    quantite = models.PositiveIntegerField(
        "quantité", validators=[MinValueValidator(1)]
    )
    numero_lot = models.CharField("numéro de lot", max_length=80)
    date_peremption = models.DateField("date de péremption")
    lot = models.ForeignKey(
        LotStock,
        on_delete=models.PROTECT,
        related_name="lignes_reception",
        verbose_name="lot de stock",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "ligne de réception"
        verbose_name_plural = "lignes de réception"
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantite__gte=0),
                name="lignereception_quantite_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["ligne_achat"]),
            models.Index(fields=["reception", "ligne_achat"]),
        ]

    def __str__(self):
        return f"{self.ligne_achat.medicament} x {self.quantite} (lot {self.numero_lot})"

    @property
    def prix_unitaire(self):
        return self.ligne_achat.prix_unitaire

    @property
    def montant_ligne(self):
        return self.prix_unitaire * self.quantite
