from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from utilisateurs.roles import MODES, ROLES, ROLE_PERMISSIONS, TOUS


class Command(BaseCommand):
    help = (
        "Crée ou met à jour les cinq groupes de rôles et leurs permissions. "
        "La commande est idempotente : relancez-la après chaque ajout de modèles."
    )

    def handle(self, *args, **options):
        applications_sans_permission = set()

        with transaction.atomic():
            for nom_role in ROLES:
                groupe, cree = Group.objects.get_or_create(name=nom_role)
                permissions = self._permissions_du_role(
                    nom_role, applications_sans_permission
                )
                groupe.permissions.set(permissions)

                etat = "Créé" if cree else "Mis à jour"
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{etat} : {nom_role} ({len(permissions)} permissions)"
                    )
                )

        for application in sorted(applications_sans_permission):
            self.stdout.write(
                self.style.WARNING(
                    f"Aucune permission disponible pour « {application} » "
                    "(modèles absents ou non migrés)."
                )
            )

        self.stdout.write(self.style.SUCCESS("Les rôles PharmaGest sont à jour."))

    def _permissions_du_role(self, nom_role, applications_sans_permission):
        cibles = ROLE_PERMISSIONS[nom_role]
        if cibles == TOUS:
            return list(Permission.objects.all())

        permissions = {}
        for application, mode in cibles.items():
            if mode not in MODES:
                raise ValueError(
                    f"Mode de permission inconnu « {mode} » pour {application}."
                )
            filtre = Q()
            for action in MODES[mode]:
                filtre |= Q(codename__startswith=f"{action}_")

            permissions_application = Permission.objects.filter(
                filtre, content_type__app_label=application
            )
            if not permissions_application.exists():
                applications_sans_permission.add(application)
            for permission in permissions_application:
                permissions[permission.pk] = permission
        return list(permissions.values())
