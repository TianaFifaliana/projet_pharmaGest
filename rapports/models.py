from django.conf import settings
from django.db import models


class JournalAudit(models.Model):
    class Action(models.TextChoices):
        CREATION = "creation", "Création"
        MODIFICATION = "modification", "Modification"
        SUPPRESSION = "suppression", "Suppression"
        VALIDATION = "validation", "Validation"
        ANNULATION = "annulation", "Annulation"
        CONNEXION = "connexion", "Connexion"
        DECONNEXION = "deconnexion", "Déconnexion"
        AUTRE = "autre", "Autre"

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="journal_audit",
        verbose_name="utilisateur",
        null=True,
        blank=True,
    )
    action = models.CharField("action", max_length=20, choices=Action.choices)
    modele = models.CharField("modèle concerné", max_length=100)
    objet_id = models.CharField("identifiant de l'objet", max_length=50, blank=True)
    description = models.TextField("description", blank=True)
    adresse_ip = models.GenericIPAddressField("adresse IP", null=True, blank=True)
    date_action = models.DateTimeField("date de l'action", auto_now_add=True)

    class Meta:
        verbose_name = "entrée du journal d'audit"
        verbose_name_plural = "journal d'audit"
        ordering = ["-date_action", "-pk"]
        indexes = [
            models.Index(fields=["modele", "objet_id"]),
            models.Index(fields=["utilisateur", "-date_action"]),
            models.Index(fields=["-date_action"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} {self.modele} #{self.objet_id}"
