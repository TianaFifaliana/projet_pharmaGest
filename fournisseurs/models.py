from django.db import models


class Fournisseur(models.Model):
    nom = models.CharField("nom", max_length=150, unique=True)
    contact = models.CharField("personne de contact", max_length=150, blank=True)
    telephone = models.CharField("téléphone", max_length=20, blank=True)
    email = models.EmailField("adresse e-mail", blank=True)
    adresse = models.CharField("adresse", max_length=255, blank=True)
    ville = models.CharField("ville", max_length=100, blank=True)
    actif = models.BooleanField("actif", default=True)
    date_creation = models.DateTimeField("date de création", auto_now_add=True)

    class Meta:
        verbose_name = "fournisseur"
        verbose_name_plural = "fournisseurs"
        ordering = ["nom"]
        indexes = [
            models.Index(fields=["actif"]),
            models.Index(fields=["ville"]),
        ]

    def __str__(self):
        return self.nom
