from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    telephone = models.CharField("téléphone", max_length=20, blank=True)

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"
        ordering = ["username"]

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def noms_roles(self):
        return list(self.groups.values_list("name", flat=True).order_by("name"))

    def a_un_role(self, *noms):
        return self.groups.filter(name__in=noms).exists()
