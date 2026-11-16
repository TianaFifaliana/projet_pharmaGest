from datetime import timedelta
from io import BytesIO, StringIO
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from stock.models import LotStock
from utilisateurs.models import User
from utilisateurs.roles import ADMINISTRATEUR, CAISSIER, GESTIONNAIRE_STOCK

from .forms import FormulaireMedicament, valider_photo
from .models import Categorie, Medicament


def image_bytes(format="PNG", size=(20, 20)):
    tampon = BytesIO()
    Image.new("RGB", size, "white").save(tampon, format=format)
    return tampon.getvalue()


def donnees_medicament(categorie, **extra):
    donnees = {
        "nom_commercial": "Doliprane",
        "nom_generique": "Paracétamol",
        "categorie": categorie.pk,
        "forme": Medicament.Forme.COMPRIME,
        "prix_achat": "1.00",
        "prix_vente": "2.00",
        "seuil_alerte": "5",
        "statut": Medicament.Statut.ACTIF,
    }
    donnees.update(extra)
    return donnees


class BaseMedicamentsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("creer_groupes", stdout=StringIO())
        cls.categorie = Categorie.objects.create(nom="Antalgiques")
        cls.administrateur = User.objects.create_user(
            "admin", password="MotDePasse123!"
        )
        cls.administrateur.groups.add(Group.objects.get(name=ADMINISTRATEUR))
        cls.gestionnaire = User.objects.create_user(
            "gestionnaire", password="MotDePasse123!"
        )
        cls.gestionnaire.groups.add(Group.objects.get(name=GESTIONNAIRE_STOCK))
        cls.caissier = User.objects.create_user(
            "caissier", password="MotDePasse123!"
        )
        cls.caissier.groups.add(Group.objects.get(name=CAISSIER))

    def creer_medicament(self, **extra):
        donnees = {
            "nom_commercial": "Doliprane",
            "categorie": self.categorie,
            "prix_achat": "1.00",
            "prix_vente": "2.00",
        }
        donnees.update(extra)
        return Medicament.objects.create(**donnees)


class PermissionsMedicamentsTests(BaseMedicamentsTests):
    def test_liste_exige_une_connexion(self):
        reponse = self.client.get(reverse("medicaments:liste"))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn(reverse("utilisateurs:connexion"), reponse.url)

    def test_caissier_peut_consulter_le_catalogue(self):
        self.client.force_login(self.caissier)
        reponse = self.client.get(reverse("medicaments:liste"))
        self.assertEqual(reponse.status_code, 200)

    def test_caissier_ne_peut_pas_creer(self):
        self.client.force_login(self.caissier)
        reponse = self.client.get(reverse("medicaments:creation"))
        self.assertEqual(reponse.status_code, 403)

    def test_gestionnaire_peut_creer_mais_pas_supprimer(self):
        self.client.force_login(self.gestionnaire)
        reponse = self.client.post(
            reverse("medicaments:creation"),
            donnees_medicament(self.categorie),
        )
        self.assertEqual(reponse.status_code, 302)
        medicament = Medicament.objects.get(nom_commercial="Doliprane")
        reponse = self.client.get(
            reverse("medicaments:suppression", args=[medicament.pk])
        )
        self.assertEqual(reponse.status_code, 403)

    def test_administrateur_accede_a_toutes_les_vues(self):
        self.client.force_login(self.administrateur)
        for nom in (
            "medicaments:liste",
            "medicaments:creation",
            "medicaments:categories",
            "medicaments:categorie_creation",
        ):
            reponse = self.client.get(reverse(nom))
            self.assertEqual(reponse.status_code, 200, nom)


class RechercheMedicamentsTests(BaseMedicamentsTests):
    def setUp(self):
        self.medicament = self.creer_medicament(code_barres="3400930000000")
        self.autre = self.creer_medicament(
            nom_commercial="Amoxicilline",
            categorie=Categorie.objects.create(nom="Antibiotiques"),
            code_barres="3400931111111",
        )
        self.client.force_login(self.caissier)

    def test_recherche_par_nom(self):
        reponse = self.client.get(reverse("medicaments:liste"), {"q": "amoxi"})
        self.assertContains(reponse, "Amoxicilline")
        self.assertNotContains(reponse, "Doliprane")

    def test_recherche_par_code_barres(self):
        reponse = self.client.get(
            reverse("medicaments:liste"), {"q": "3400930000000"}
        )
        self.assertContains(reponse, "Doliprane")
        self.assertNotContains(reponse, "Amoxicilline")

    def test_filtre_par_categorie(self):
        reponse = self.client.get(
            reverse("medicaments:liste"), {"categorie": self.autre.categorie_id}
        )
        self.assertContains(reponse, "Amoxicilline")
        self.assertNotContains(reponse, "Doliprane")

    def test_tri_par_prix_decroissant(self):
        self.medicament.prix_vente = "10.00"
        self.medicament.save(update_fields=["prix_vente"])
        reponse = self.client.get(reverse("medicaments:liste"), {"tri": "-prix"})
        contenu = reponse.content.decode()
        self.assertLess(contenu.index("Doliprane"), contenu.index("Amoxicilline"))

    def test_detail_affiche_le_medicament(self):
        reponse = self.client.get(
            reverse("medicaments:detail", args=[self.medicament.pk])
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Doliprane")
        self.assertContains(reponse, "Historique")


class ValidationMedicamentTests(BaseMedicamentsTests):
    def test_code_barres_unique(self):
        self.creer_medicament(code_barres="CODE-001")
        formulaire = FormulaireMedicament(
            donnees_medicament(self.categorie, code_barres="CODE-001")
        )
        self.assertFalse(formulaire.is_valid())
        self.assertIn("code_barres", formulaire.errors)

    def test_prix_positifs(self):
        formulaire = FormulaireMedicament(
            donnees_medicament(self.categorie, prix_achat="0", prix_vente="-1")
        )
        self.assertFalse(formulaire.is_valid())
        self.assertIn("prix_achat", formulaire.errors)
        self.assertIn("prix_vente", formulaire.errors)

    def test_photo_valide_acceptee(self):
        fichier = SimpleUploadedFile(
            "photo.png", image_bytes("PNG"), content_type="image/png"
        )
        formulaire = FormulaireMedicament(
            donnees_medicament(self.categorie), files={"photo": fichier}
        )
        self.assertTrue(formulaire.is_valid(), formulaire.errors)

    def test_photo_format_refuse(self):
        fichier = SimpleUploadedFile(
            "photo.gif", image_bytes("GIF"), content_type="image/gif"
        )
        with self.assertRaises(ValidationError):
            valider_photo(fichier)

    def test_photo_trop_volumineuse_refusee(self):
        fichier = SimpleUploadedFile(
            "photo.png", image_bytes("PNG"), content_type="image/png"
        )
        with patch("medicaments.forms.TAILLE_MAX_PHOTO", 10):
            with self.assertRaises(ValidationError):
                valider_photo(fichier)

    def test_fichier_non_image_refuse(self):
        fichier = SimpleUploadedFile(
            "faux.png", b"ceci n'est pas une image", content_type="image/png"
        )
        with self.assertRaises(ValidationError):
            valider_photo(fichier)


class SuppressionMedicamentTests(BaseMedicamentsTests):
    def setUp(self):
        self.client.force_login(self.administrateur)

    def test_suppression_sans_historique(self):
        medicament = self.creer_medicament()
        reponse = self.client.post(
            reverse("medicaments:suppression", args=[medicament.pk])
        )
        self.assertRedirects(reponse, reverse("medicaments:liste"))
        self.assertFalse(Medicament.objects.filter(pk=medicament.pk).exists())

    def test_archivage_automatique_avec_historique(self):
        medicament = self.creer_medicament()
        LotStock.objects.create(
            medicament=medicament,
            numero_lot="LOT-1",
            date_peremption=timezone.localdate() + timedelta(days=365),
            quantite_recue=10,
            quantite_disponible=10,
        )
        reponse = self.client.post(
            reverse("medicaments:suppression", args=[medicament.pk]),
            follow=True,
        )
        medicament.refresh_from_db()
        self.assertEqual(medicament.statut, Medicament.Statut.ARCHIVE)
        self.assertContains(reponse, "archivé")

    def test_confirmation_avant_suppression(self):
        medicament = self.creer_medicament()
        reponse = self.client.get(
            reverse("medicaments:suppression", args=[medicament.pk])
        )
        self.assertContains(reponse, "Confirmer")
        self.assertTrue(Medicament.objects.filter(pk=medicament.pk).exists())


class CategoriesTests(BaseMedicamentsTests):
    def setUp(self):
        self.client.force_login(self.administrateur)

    def test_recherche_categorie(self):
        Categorie.objects.create(nom="Vitamines")
        reponse = self.client.get(
            reverse("medicaments:categories"), {"q": "vita"}
        )
        self.assertContains(reponse, "Vitamines")
        self.assertNotContains(reponse, "Antalgiques")

    def test_suppression_bloquee_si_utilisee(self):
        self.creer_medicament()
        reponse = self.client.post(
            reverse("medicaments:categorie_suppression", args=[self.categorie.pk]),
            follow=True,
        )
        self.assertTrue(Categorie.objects.filter(pk=self.categorie.pk).exists())
        self.assertContains(reponse, "ne peut pas être supprimée")

    def test_suppression_autorisee_si_non_utilisee(self):
        categorie = Categorie.objects.create(nom="Inutilisée")
        reponse = self.client.post(
            reverse("medicaments:categorie_suppression", args=[categorie.pk])
        )
        self.assertRedirects(reponse, reverse("medicaments:categories"))
        self.assertFalse(Categorie.objects.filter(pk=categorie.pk).exists())

    def test_nom_categorie_unique(self):
        formulaire_reponse = self.client.post(
            reverse("medicaments:categorie_creation"),
            {"nom": self.categorie.nom, "description": ""},
        )
        self.assertEqual(formulaire_reponse.status_code, 200)
        self.assertEqual(
            Categorie.objects.filter(nom=self.categorie.nom).count(), 1
        )
