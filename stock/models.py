from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from medicaments.models import Medicament


class LotStock(models.Model):
    medicament = models.ForeignKey(
        Medicament,
        on_delete=models.PROTECT,
        related_name="lots",
        verbose_name="médicament",
    )
    numero_lot = models.CharField("numéro de lot", max_length=80)
    date_peremption = models.DateField("date de péremption")
    quantite_recue = models.PositiveIntegerField(
        "quantité reçue", default=0, validators=[MinValueValidator(0)]
    )
    quantite_disponible = models.PositiveIntegerField(
        "quantité disponible", default=0, validators=[MinValueValidator(0)]
    )
    bloque = models.BooleanField("lot bloqué", default=False)
    date_reception = models.DateTimeField("date de réception", auto_now_add=True)

    class Meta:
        verbose_name = "lot de stock"
        verbose_name_plural = "lots de stock"
        ordering = ["date_peremption", "numero_lot"]
        constraints = [
            models.UniqueConstraint(
                fields=["medicament", "numero_lot"],
                name="lotstock_medicament_numero_lot_unique",
            ),
            models.CheckConstraint(
                condition=Q(quantite_recue__gte=0),
                name="lotstock_quantite_recue_positive",
            ),
            models.CheckConstraint(
                condition=Q(quantite_disponible__gte=0),
                name="lotstock_quantite_disponible_positive",
            ),
            models.CheckConstraint(
                condition=Q(quantite_disponible__lte=F("quantite_recue")),
                name="lotstock_disponible_inferieure_ou_egale_recue",
            ),
        ]
        indexes = [
            models.Index(fields=["medicament", "date_peremption"]),
            models.Index(fields=["date_peremption", "bloque"]),
            models.Index(fields=["medicament", "bloque"]),
        ]

    def __str__(self):
        return (
            f"{self.medicament} - lot {self.numero_lot} "
            f"(exp. {self.date_peremption:%d/%m/%Y})"
        )

    @property
    def est_perime(self):
        return self.date_peremption < timezone.localdate()

    @property
    def est_vendable(self):
        return not self.bloque and not self.est_perime and self.quantite_disponible > 0


class MouvementStock(models.Model):
    class TypeMouvement(models.TextChoices):
        ENTREE = "entree", "Entrée"
        SORTIE = "sortie", "Sortie"
        RETOUR = "retour", "Retour"
        CORRECTION = "correction", "Correction"

    type_mouvement = models.CharField(
        "type de mouvement", max_length=12, choices=TypeMouvement.choices
    )
    quantite = models.PositiveIntegerField(
        "quantité", validators=[MinValueValidator(0)]
    )
    lot = models.ForeignKey(
        LotStock,
        on_delete=models.PROTECT,
        related_name="mouvements",
        verbose_name="lot",
    )
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="mouvements_stock",
        verbose_name="auteur",
        editable=False,
    )
    date_mouvement = models.DateTimeField("date du mouvement", auto_now_add=True)
    reference = models.CharField("référence", max_length=100, blank=True)
    commentaire = models.TextField("commentaire", blank=True)

    class Meta:
        verbose_name = "mouvement de stock"
        verbose_name_plural = "mouvements de stock"
        ordering = ["-date_mouvement", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantite__gte=0),
                name="mouvementstock_quantite_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["lot", "type_mouvement"]),
            models.Index(fields=["date_mouvement"]),
            models.Index(fields=["auteur"]),
        ]

    def __str__(self):
        return (
            f"{self.get_type_mouvement_display()} de {self.quantite} "
            f"- {self.lot.numero_lot}"
        )
