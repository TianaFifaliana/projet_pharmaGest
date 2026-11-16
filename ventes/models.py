from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from clients.models import Client
from stock.models import LotStock


def generer_numero_vente():
    return f"VT-{timezone.localdate():%Y%m%d}-{uuid4().hex[:6].upper()}"


class Vente(models.Model):
    class Statut(models.TextChoices):
        BROUILLON = "brouillon", "Brouillon"
        VALIDEE = "validee", "Validée"
        ANNULEE = "annulee", "Annulée"

    numero = models.CharField(
        "numéro",
        max_length=30,
        unique=True,
        editable=False,
        default=generer_numero_vente,
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        related_name="ventes",
        verbose_name="client",
        null=True,
        blank=True,
    )
    statut = models.CharField(
        "statut", max_length=20, choices=Statut.choices, default=Statut.BROUILLON
    )
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ventes",
        verbose_name="auteur",
        editable=False,
    )
    date_validation = models.DateTimeField("date de validation", null=True, blank=True)
    commentaire = models.TextField("commentaire", blank=True)
    date_creation = models.DateTimeField("date de création", auto_now_add=True)

    class Meta:
        verbose_name = "vente"
        verbose_name_plural = "ventes"
        ordering = ["-date_creation", "-pk"]
        indexes = [
            models.Index(fields=["statut"]),
            models.Index(fields=["client", "statut"]),
            models.Index(fields=["-date_creation"]),
        ]

    def __str__(self):
        return f"{self.numero} - {self.client or 'Client comptoir'}"

    @property
    def montant_total(self):
        return sum(
            (ligne.total_ligne for ligne in self.lignes.all()), Decimal("0.00")
        )

    @property
    def montant_paye(self):
        return sum(
            (
                paiement.montant
                for paiement in self.paiements.filter(statut=Paiement.Statut.VALIDE)
            ),
            Decimal("0.00"),
        )

    @property
    def est_modifiable(self):
        return self.statut == self.Statut.BROUILLON


class LigneVente(models.Model):
    vente = models.ForeignKey(
        Vente,
        on_delete=models.CASCADE,
        related_name="lignes",
        verbose_name="vente",
    )
    lot = models.ForeignKey(
        LotStock,
        on_delete=models.PROTECT,
        related_name="lignes_vente",
        verbose_name="lot",
    )
    quantite = models.PositiveIntegerField(
        "quantité", validators=[MinValueValidator(1)]
    )
    prix_applique = models.DecimalField(
        "prix appliqué",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        verbose_name = "ligne de vente"
        verbose_name_plural = "lignes de vente"
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantite__gte=0),
                name="lignevente_quantite_positive",
            ),
            models.CheckConstraint(
                condition=Q(prix_applique__gte=0),
                name="lignevente_prix_applique_positif",
            ),
        ]
        indexes = [
            models.Index(fields=["lot"]),
        ]

    def __str__(self):
        return f"{self.lot.medicament} x {self.quantite}"

    @property
    def medicament(self):
        return self.lot.medicament

    @property
    def total_ligne(self):
        return self.prix_applique * self.quantite

    @property
    def quantite_retournee(self):
        return sum((r.quantite for r in self.retours.all()), 0)

    @property
    def quantite_retournable(self):
        return max(0, self.quantite - self.quantite_retournee)


class Paiement(models.Model):
    class Mode(models.TextChoices):
        ESPECES = "especes", "Espèces"
        MOBILE_MONEY = "mobile_money", "Mobile money"
        CARTE = "carte", "Carte bancaire"
        CHEQUE = "cheque", "Chèque"
        VIREMENT = "virement", "Virement"
        CREDIT = "credit", "Crédit"

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        VALIDE = "valide", "Validé"
        ANNULE = "annule", "Annulé"

    vente = models.ForeignKey(
        Vente,
        on_delete=models.CASCADE,
        related_name="paiements",
        verbose_name="vente",
    )
    mode = models.CharField("mode de paiement", max_length=20, choices=Mode.choices)
    statut = models.CharField(
        "statut", max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE
    )
    montant = models.DecimalField(
        "montant",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="paiements",
        verbose_name="auteur",
        editable=False,
    )
    date_paiement = models.DateTimeField("date de paiement", auto_now_add=True)

    class Meta:
        verbose_name = "paiement"
        verbose_name_plural = "paiements"
        ordering = ["-date_paiement", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(montant__gte=0),
                name="paiement_montant_positif",
            ),
        ]
        indexes = [
            models.Index(fields=["vente", "statut"]),
            models.Index(fields=["date_paiement"]),
        ]

    def __str__(self):
        return f"{self.get_mode_display()} - {self.montant}"


class RetourVente(models.Model):
    class TypeRetour(models.TextChoices):
        RETOUR_LIGNE = "retour_ligne", "Retour de ligne"
        ANNULATION = "annulation", "Annulation de vente"

    vente = models.ForeignKey(
        Vente,
        on_delete=models.PROTECT,
        related_name="retours",
        verbose_name="vente",
    )
    ligne_vente = models.ForeignKey(
        LigneVente,
        on_delete=models.PROTECT,
        related_name="retours",
        verbose_name="ligne de vente",
        null=True,
        blank=True,
    )
    lot = models.ForeignKey(
        LotStock,
        on_delete=models.PROTECT,
        related_name="retours_vente",
        verbose_name="lot",
        null=True,
        blank=True,
    )
    quantite = models.PositiveIntegerField("quantité retournée", default=0)
    reintegrable = models.BooleanField("réintégrable en stock", default=False)
    type_retour = models.CharField(
        "type de retour",
        max_length=20,
        choices=TypeRetour.choices,
        default=TypeRetour.RETOUR_LIGNE,
    )
    montant = models.DecimalField(
        "montant remboursé",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    motif = models.TextField("motif")
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="retours_vente",
        verbose_name="auteur",
        editable=False,
    )
    date_creation = models.DateTimeField("date du retour", auto_now_add=True)

    class Meta:
        verbose_name = "retour de vente"
        verbose_name_plural = "retours de vente"
        ordering = ["-date_creation", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(montant__gte=0),
                name="retourvente_montant_positif",
            ),
            models.CheckConstraint(
                condition=Q(quantite__gte=0),
                name="retourvente_quantite_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["vente"]),
            models.Index(fields=["ligne_vente"]),
        ]

    def __str__(self):
        cible = self.ligne_vente_id or self.vente_id
        return f"Retour {self.vente.numero} ({cible}) - {self.montant}"
