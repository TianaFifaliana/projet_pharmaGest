from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


def chemin_photo(instance, nom_fichier):
    return f"medicaments/{uuid4().hex}{Path(nom_fichier).suffix.lower()}"


class Categorie(models.Model):
    nom = models.CharField("nom", max_length=100, unique=True)
    description = models.TextField("description", blank=True)
    date_creation = models.DateTimeField("date de création", auto_now_add=True)

    class Meta:
        verbose_name = "catégorie"
        verbose_name_plural = "catégories"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Medicament(models.Model):
    class Forme(models.TextChoices):
        COMPRIME = "comprime", "Comprimé"
        GELULE = "gelule", "Gélule"
        SIROP = "sirop", "Sirop"
        INJECTABLE = "injectable", "Injectable"
        POMMADE = "pommade", "Pommade"
        CREME = "creme", "Crème"
        SUPPOSITOIRE = "suppositoire", "Suppositoire"
        COLLYRE = "collyre", "Collyre"
        AUTRE = "autre", "Autre"

    class Statut(models.TextChoices):
        ACTIF = "actif", "Actif"
        ARCHIVE = "archive", "Archivé"

    nom_commercial = models.CharField("nom commercial", max_length=150)
    nom_generique = models.CharField("nom générique", max_length=150, blank=True)
    categorie = models.ForeignKey(
        Categorie,
        on_delete=models.PROTECT,
        related_name="medicaments",
        verbose_name="catégorie",
    )
    forme = models.CharField(
        "forme", max_length=20, choices=Forme.choices, default=Forme.COMPRIME
    )
    dosage = models.CharField("dosage", max_length=50, blank=True)
    laboratoire = models.CharField("laboratoire", max_length=150, blank=True)
    code_barres = models.CharField(
        "code-barres", max_length=64, unique=True, null=True, blank=True
    )
    photo = models.ImageField(
        "photo", upload_to=chemin_photo, null=True, blank=True
    )
    prix_achat = models.DecimalField(
        "prix d'achat",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    prix_vente = models.DecimalField(
        "prix de vente",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    seuil_alerte = models.PositiveIntegerField(
        "seuil d'alerte", default=10, validators=[MinValueValidator(0)]
    )
    statut = models.CharField(
        "statut", max_length=10, choices=Statut.choices, default=Statut.ACTIF
    )
    date_creation = models.DateTimeField("date de création", auto_now_add=True)
    date_modification = models.DateTimeField("date de modification", auto_now=True)

    class Meta:
        verbose_name = "médicament"
        verbose_name_plural = "médicaments"
        ordering = ["nom_commercial"]
        constraints = [
            models.CheckConstraint(
                condition=Q(prix_achat__gte=0),
                name="medicament_prix_achat_positif",
            ),
            models.CheckConstraint(
                condition=Q(prix_vente__gte=0),
                name="medicament_prix_vente_positif",
            ),
            models.CheckConstraint(
                condition=Q(seuil_alerte__gte=0),
                name="medicament_seuil_alerte_positif",
            ),
        ]
        indexes = [
            models.Index(fields=["nom_commercial"]),
            models.Index(fields=["nom_generique"]),
            models.Index(fields=["statut"]),
            models.Index(fields=["categorie", "statut"]),
        ]

    def __str__(self):
        libelle = self.nom_commercial
        if self.dosage:
            libelle = f"{libelle} {self.dosage}"
        return libelle

    @property
    def a_un_historique(self):
        """Vrai si le médicament est référencé par du stock ou des achats."""
        return self.lots.exists() or self.lignes_achat.exists()

    def save(self, *args, **kwargs):
        if self.code_barres is not None:
            self.code_barres = self.code_barres.strip() or None
        super().save(*args, **kwargs)
