from io import StringIO

from django.contrib.auth.models import Group, Permission
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import User
from .roles import ADMINISTRATEUR, CAISSIER, PHARMACIEN_RESPONSABLE, ROLES


class RolesTests(TestCase):
    def setUp(self):
        call_command("creer_groupes", stdout=StringIO())

    def test_les_cinq_roles_sont_crees(self):
        self.assertEqual(Group.objects.filter(name__in=ROLES).count(), 5)

    def test_commande_idempotente(self):
        call_command("creer_groupes", stdout=StringIO())
        self.assertEqual(Group.objects.filter(name__in=ROLES).count(), 5)

    def test_administrateur_possede_toutes_les_permissions(self):
        groupe = Group.objects.get(name=ADMINISTRATEUR)
        self.assertEqual(groupe.permissions.count(), Permission.objects.count())

    def test_caissier_sans_permission_de_suppression(self):
        groupe = Group.objects.get(name=CAISSIER)
        self.assertFalse(groupe.permissions.filter(codename__startswith="delete_").exists())

    def test_caissier_sans_gestion_des_comptes(self):
        groupe = Group.objects.get(name=CAISSIER)
        self.assertFalse(
            groupe.permissions.filter(content_type__app_label="utilisateurs").exists()
        )


class AccesUtilisateursTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("creer_groupes", stdout=StringIO())
        cls.administrateur = User.objects.create_user(
            "administrateur", password="MotDePasse123!"
        )
        cls.administrateur.groups.add(Group.objects.get(name=ADMINISTRATEUR))
        cls.caissier = User.objects.create_user("caissier", password="MotDePasse123!")
        cls.caissier.groups.add(Group.objects.get(name=CAISSIER))

    def test_liste_exige_une_connexion(self):
        reponse = self.client.get(reverse("utilisateurs:liste"))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn(reverse("utilisateurs:connexion"), reponse.url)

    def test_caissier_refuse_sur_la_liste(self):
        self.client.force_login(self.caissier)
        reponse = self.client.get(reverse("utilisateurs:liste"))
        self.assertEqual(reponse.status_code, 403)
        self.assertContains(reponse, "droits nécessaires", status_code=403)

    def test_administrateur_autorise_sur_la_liste(self):
        self.client.force_login(self.administrateur)
        reponse = self.client.get(reverse("utilisateurs:liste"))
        self.assertEqual(reponse.status_code, 200)

    def test_creation_compte_avec_deux_roles(self):
        self.client.force_login(self.administrateur)
        roles = Group.objects.filter(name__in=[CAISSIER, PHARMACIEN_RESPONSABLE])
        reponse = self.client.post(
            reverse("utilisateurs:creation"),
            {
                "username": "nouveau",
                "first_name": "Nou",
                "last_name": "Veau",
                "email": "nouveau@example.com",
                "telephone": "0340000000",
                "password1": "MotDePasse123!",
                "password2": "MotDePasse123!",
                "is_active": "on",
                "groups": [role.pk for role in roles],
            },
        )
        self.assertRedirects(reponse, reverse("utilisateurs:liste"))
        utilisateur = User.objects.get(username="nouveau")
        self.assertEqual(utilisateur.groups.count(), 2)
        self.assertTrue(utilisateur.is_active)

    def test_auto_desactivation_interdite(self):
        self.client.force_login(self.administrateur)
        reponse = self.client.post(
            reverse("utilisateurs:desactiver", args=[self.administrateur.pk])
        )
        self.assertRedirects(reponse, reverse("utilisateurs:liste"))
        self.administrateur.refresh_from_db()
        self.assertTrue(self.administrateur.is_active)

    def test_dernier_administrateur_non_desactivable(self):
        racine = User.objects.create_superuser(
            "racine", "racine@example.com", "MotDePasse123!"
        )
        self.client.force_login(racine)
        reponse = self.client.post(
            reverse("utilisateurs:desactiver", args=[self.administrateur.pk])
        )
        self.assertRedirects(reponse, reverse("utilisateurs:liste"))
        self.administrateur.refresh_from_db()
        self.assertTrue(self.administrateur.is_active)

    def test_caissier_ne_peut_pas_creer_de_compte(self):
        self.client.force_login(self.caissier)
        reponse = self.client.get(reverse("utilisateurs:creation"))
        self.assertEqual(reponse.status_code, 403)

    def test_compte_inactif_ne_peut_pas_se_connecter(self):
        self.caissier.is_active = False
        self.caissier.save(update_fields=["is_active"])
        self.assertFalse(
            self.client.login(username="caissier", password="MotDePasse123!")
        )

    def test_changement_mot_de_passe_exige_connexion(self):
        reponse = self.client.get(reverse("utilisateurs:changement_mot_de_passe"))
        self.assertEqual(reponse.status_code, 302)

    def test_reinitialisation_envoie_un_email(self):
        self.administrateur.email = "administrateur@example.com"
        self.administrateur.save(update_fields=["email"])
        reponse = self.client.post(
            reverse("utilisateurs:reinitialisation_mot_de_passe"),
            {"email": "administrateur@example.com"},
        )
        self.assertRedirects(
            reponse, reverse("utilisateurs:reinitialisation_mot_de_passe_envoyee")
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("réinitialisation", mail.outbox[0].subject.lower())
