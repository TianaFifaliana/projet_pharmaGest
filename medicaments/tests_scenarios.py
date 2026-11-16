from datetime import timedelta
from decimal import Decimal
from io import BytesIO, StringIO

from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from achats.models import CommandeAchat, LigneAchat, ReceptionAchat
from achats.services import changer_statut, valider_reception
from medicaments.models import Categorie, Medicament
from stock.models import LotStock, MouvementStock
from utilisateurs.models import User
from utilisateurs.roles import ADMINISTRATEUR, CAISSIER, GESTIONNAIRE_STOCK, PHARMACIEN_RESPONSABLE


def image_upload(name="photo.png", fmt="PNG"):
    buf = BytesIO()
    Image.new("RGB", (10, 10), "white").save(buf, format=fmt)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{fmt.lower()}")


def make_user(username, role=None, password="MotDePasse123!", **extra):
    user = User.objects.create_user(username, password=password, **extra)
    if role:
        user.groups.add(Group.objects.get(name=role))
    return user


def make_categorie(nom="Antalgiques"):
    return Categorie.objects.create(nom=nom)


def make_medicament(categorie=None, **extra):
    if categorie is None:
        categorie = make_categorie(nom=extra.pop("cat_nom", "Categorie"))
    data = {
        "nom_commercial": extra.pop("nom_commercial", "Doliprane"),
        "categorie": categorie,
        "forme": Medicament.Forme.COMPRIME,
        "prix_achat": Decimal("100.00"),
        "prix_vente": Decimal("200.00"),
        "seuil_alerte": 5,
        "statut": Medicament.Statut.ACTIF,
    }
    data.update(extra)
    return Medicament.objects.create(**data)


def make_commande_receptionnable(fournisseur_user, medicament, quantite=20):
    from fournisseurs.models import Fournisseur

    fournisseur = Fournisseur.objects.create(nom="Fournisseur Test")
    commande = CommandeAchat.objects.create(fournisseur=fournisseur, auteur=fournisseur_user, statut=CommandeAchat.Statut.BROUILLON)
    ligne = LigneAchat.objects.create(commande=commande, medicament=medicament, quantite=quantite, prix_unitaire=Decimal("100.00"))
    changer_statut(commande, CommandeAchat.Statut.COMMANDEE, utilisateur=fournisseur_user)
    return commande, ligne


class ScenarioMedicamentsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("creer_groupes", stdout=StringIO())

    def setUp(self):
        self.admin = make_user("adminm", ADMINISTRATEUR)
        self.gestionnaire = make_user("gestm", GESTIONNAIRE_STOCK)
        self.caissier = make_user("caissm", CAISSIER)
        self.categorie = make_categorie("Douleurs")

    def test_1_ajouter_medicament_avec_photo(self):
        self.client.force_login(self.gestionnaire)
        url = reverse("medicaments:creation")
        data = {
            "nom_commercial": "Ibuprofene",
            "nom_generique": "Ibuprofene",
            "categorie": self.categorie.pk,
            "forme": Medicament.Forme.COMPRIME,
            "dosage": "400mg",
            "laboratoire": "Lab",
            "code_barres": "",
            "prix_achat": "50.00",
            "prix_vente": "120.00",
            "seuil_alerte": "10",
            "statut": Medicament.Statut.ACTIF,
        }
        resp = self.client.post(url, {**data, "photo": image_upload()}, follow=False)
        self.assertEqual(resp.status_code, 302)
        med = Medicament.objects.get(nom_commercial="Ibuprofene")
        self.assertTrue(med.photo)

    def test_2_modifier_medicament(self):
        med = make_medicament(categorie=self.categorie, nom_commercial="Amodifier")
        self.client.force_login(self.gestionnaire)
        url = reverse("medicaments:modification", args=[med.pk])
        data = {
            "nom_commercial": "Modifie",
            "nom_generique": "",
            "categorie": self.categorie.pk,
            "forme": Medicament.Forme.SIROP,
            "dosage": "100ml",
            "laboratoire": "LaboX",
            "code_barres": "",
            "prix_achat": "80.00",
            "prix_vente": "150.00",
            "seuil_alerte": "7",
            "statut": Medicament.Statut.ACTIF,
        }
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302)
        med.refresh_from_db()
        self.assertEqual(med.nom_commercial, "Modifie")
        self.assertEqual(med.prix_vente, Decimal("150.00"))

    def test_3_archiver_au_lieu_de_supprimer(self):
        med = make_medicament(categorie=self.categorie, nom_commercial="Historique")
        LotStock.objects.create(
            medicament=med,
            numero_lot="LOT-H",
            date_peremption=timezone.localdate() + timedelta(days=365),
            quantite_recue=5,
            quantite_disponible=5,
        )
        self.client.force_login(self.admin)
        resp = self.client.post(reverse("medicaments:suppression", args=[med.pk]), follow=True)
        self.assertEqual(resp.status_code, 200)
        med.refresh_from_db()
        self.assertTrue(Medicament.objects.filter(pk=med.pk).exists())
        self.assertEqual(med.statut, Medicament.Statut.ARCHIVE)

    def test_8_acces_sans_permission_403_medicament(self):
        self.client.force_login(self.caissier)
        resp = self.client.get(reverse("medicaments:creation"))
        self.assertEqual(resp.status_code, 403)
