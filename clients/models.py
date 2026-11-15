from django.db import models


class Client(models.Model):
    nom = models.CharField("nom", max_length=150)
    prenom = models.CharField("prénom", max_length=150, blank=True)
    telephone = models.CharField("téléphone", max_length=20, blank=True)
    email = models.EmailField("adresse e-mail", blank=True)
    adresse = models.CharField("adresse", max_length=255, blank=True)
    actif = models.BooleanField("actif", default=True)
    date_creation = models.DateTimeField("date de création", auto_now_add=True)

    class Meta:
        verbose_name = "client"
        verbose_name_plural = "clients"
        ordering = ["nom", "prenom"]
        indexes = [
            models.Index(fields=["nom", "prenom"]),
            models.Index(fields=["telephone"]),
            models.Index(fields=["actif"]),
        ]

    def __str__(self):
        return self.nom_complet

    @property
    def nom_complet(self):
        return f"{self.nom} {self.prenom}".strip()
