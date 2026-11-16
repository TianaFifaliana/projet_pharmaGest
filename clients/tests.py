from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from medicaments.models import Categorie, Medicament
from stock.models import LotStock
from utilisateurs.models import User
from utilisateurs.roles import (
    ADMINISTRATEUR,
    CAISSIER,
    RESPONSABLE_GESTION,
)
from ventes.models import LigneVente, Vente

from .models import Client


class BaseClientsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("creer_groupes", stdout=StringIO())
        cls.administrateur = User.objects.create_user(
            "admin", password="MotDePasse123!"
        )
        cls.administrateur.groups.add(Group.objects.get(name=ADMINISTRATEUR))
        cls.caissier = User.objects.create_user(
            "caissier", password="MotDePasse123!"
        )
        cls.caissier.groups.add(Group.objects.get(name=CAISSIER))
        cls.gestionnaire = User.objects.create_user(
            "gestionnaire", password="MotDePasse123!"
        )
        cls.gestionnaire.groups.add(Group.objects.get(name=RESPONSABLE_GESTION))

        cls.categorie = Categorie.objects.create(nom="Antalgiques")
        cls.medicament = Medicament.objects.create(
            nom_commercial="Doliprane",
            categorie=cls.categorie,
            prix_achat=Decimal("1.00"),
            prix_vente=Decimal("2.00"),
        )
        cls.lot = LotStock.objects.create(
            medicament=cls.medicament,
            numero_lot="LOT-1",
            date_peremption=timezone.localdate() + timedelta(days=365),
            quantite_recue=10,
            quantite_disponible=10,
        )

    def creer_client(self, **extra):
        donnees = {"nom": "Rakoto"}
        donnees.update(extra)
        return Client.objects.create(**donnees)

    def creer_vente(self, client, montant="3.50", quantite=2):
        vente = Vente.objects.create(
            client=client,
            auteur=self.administrateur,
            statut=Vente.Statut.VALIDEE,
            date_validation=timezone.now(),
        )
        LigneVente.objects.create(
            vente=vente,
            lot=self.lot,
            quantite=quantite,
            prix_applique=Decimal(montant),
        )
        return vente


class PermissionsClientsTests(BaseClientsTests):
    def test_liste_exige_une_connexion(self):
        reponse = self.client.get(reverse("clients:liste"))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn(reverse("utilisateurs:connexion"), reponse.url)

    def test_caissier_cree_mais_ne_desactive_pas(self):
        self.client.force_login(self.caissier)
        reponse = self.client.post(
            reverse("clients:creation"),
            {"nom": "Rasoanaivo", "actif": "on"},
        )
        self.assertEqual(reponse.status_code, 302)
        client = Client.objects.get(nom="Rasoanaivo")

        reponse = self.client.get(reverse("clients:desactiver", args=[client.pk]))
        self.assertEqual(reponse.status_code, 403)

    def test_gestionnaire_desactive_mais_ne_supprime_pas(self):
        self.client.force_login(self.gestionnaire)
        client = self.creer_client()
        reponse = self.client.post(
            reverse("clients:desactiver", args=[client.pk])
        )
        self.assertRedirects(
            reponse, reverse("clients:detail", args=[client.pk])
        )
        client.refresh_from_db()
        self.assertFalse(client.actif)

        reponse = self.client.get(
            reverse("clients:suppression", args=[client.pk])
        )
        self.assertEqual(reponse.status_code, 403)

    def test_administrateur_supprime_un_client(self):
        self.client.force_login(self.administrateur)
        client = self.creer_client()
        reponse = self.client.post(
            reverse("clients:suppression", args=[client.pk])
        )
        self.assertRedirects(reponse, reverse("clients:liste"))
        self.assertFalse(Client.objects.filter(pk=client.pk).exists())


class RechercheClientsTests(BaseClientsTests):
    def setUp(self):
        self.client_obj = self.creer_client(
            nom="Rakoto", telephone="0341111111"
        )
        self.autre = self.creer_client(
            nom="Rabe", telephone="0349999999"
        )
        self.client.force_login(self.caissier)

    def test_recherche_par_nom(self):
        reponse = self.client.get(reverse("clients:liste"), {"q": "rab"})
        self.assertContains(reponse, "Rabe")
        self.assertNotContains(reponse, "Rakoto")

    def test_recherche_par_telephone(self):
        reponse = self.client.get(
            reverse("clients:liste"), {"q": "0341111111"}
        )
        self.assertContains(reponse, "Rakoto")
        self.assertNotContains(reponse, "Rabe")

    def test_filtre_par_statut(self):
        self.autre.actif = False
        self.autre.save(update_fields=["actif"])
        reponse = self.client.get(
            reverse("clients:liste"), {"statut": "inactifs"}
        )
        self.assertContains(reponse, "Rabe")
        self.assertNotContains(reponse, "Rakoto")


class DetailClientTests(BaseClientsTests):
    def setUp(self):
        self.client.force_login(self.administrateur)
        self.client_obj = self.creer_client(nom="Rakoto", prenom="Jean")
        self.vente = self.creer_vente(self.client_obj)

    def test_historique_et_montant_des_ventes(self):
        reponse = self.client.get(
            reverse("clients:detail", args=[self.client_obj.pk])
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.context["nombre_ventes"], 1)
        self.assertEqual(reponse.context["montant_ventes"], Decimal("7.00"))
        self.assertContains(reponse, self.vente.numero)

    def test_suppression_conserve_les_ventes_en_comptoir(self):
        reponse = self.client.post(
            reverse("clients:suppression", args=[self.client_obj.pk]),
            follow=True,
        )
        self.assertFalse(
            Client.objects.filter(pk=self.client_obj.pk).exists()
        )
        vente = Vente.objects.get(pk=self.vente.pk)
        self.assertIsNone(vente.client_id)
        self.assertContains(reponse, "comptoir")

    def test_nom_obligatoire(self):
        reponse = self.client.post(
            reverse("clients:creation"), {"nom": "   ", "actif": "on"}
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "obligatoire")


class VenteComptoirTests(BaseClientsTests):
    def test_vente_sans_client(self):
        vente = Vente.objects.create(auteur=self.administrateur)
        self.assertIsNone(vente.client_id)
        self.assertIn("comptoir", str(vente).lower())


class PaginationClientsTests(BaseClientsTests):
    def test_pagination(self):
        for index in range(25):
            self.creer_client(nom=f"Client {index:02d}")
        self.client.force_login(self.caissier)
        reponse = self.client.get(reverse("clients:liste"))
        self.assertTrue(reponse.context["is_paginated"])
        self.assertEqual(len(reponse.context["clients"]), 20)
