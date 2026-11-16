from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from achats.models import (
    CommandeAchat,
    LigneAchat,
    LigneReception,
    ReceptionAchat,
)
from medicaments.models import Categorie, Medicament
from utilisateurs.models import User
from utilisateurs.roles import (
    ADMINISTRATEUR,
    PHARMACIEN_RESPONSABLE,
    RESPONSABLE_GESTION,
)

from .models import Fournisseur


class BaseFournisseursTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("creer_groupes", stdout=StringIO())
        cls.administrateur = User.objects.create_user(
            "admin", password="MotDePasse123!"
        )
        cls.administrateur.groups.add(Group.objects.get(name=ADMINISTRATEUR))
        cls.gestionnaire = User.objects.create_user(
            "gestionnaire", password="MotDePasse123!"
        )
        cls.gestionnaire.groups.add(Group.objects.get(name=RESPONSABLE_GESTION))
        cls.lecteur = User.objects.create_user(
            "lecteur", password="MotDePasse123!"
        )
        cls.lecteur.groups.add(Group.objects.get(name=PHARMACIEN_RESPONSABLE))

        cls.categorie = Categorie.objects.create(nom="Antalgiques")
        cls.medicament = Medicament.objects.create(
            nom_commercial="Doliprane",
            categorie=cls.categorie,
            prix_achat=Decimal("1.00"),
            prix_vente=Decimal("2.00"),
        )

    def creer_fournisseur(self, **extra):
        donnees = {"nom": "Pharma Distrib"}
        donnees.update(extra)
        return Fournisseur.objects.create(**donnees)

    def creer_achat(self, fournisseur, quantite=10, prix="2.00", recue=4):
        commande = CommandeAchat.objects.create(
            fournisseur=fournisseur,
            auteur=self.administrateur,
            statut=CommandeAchat.Statut.COMMANDEE,
        )
        ligne = LigneAchat.objects.create(
            commande=commande,
            medicament=self.medicament,
            quantite=quantite,
            prix_unitaire=Decimal(prix),
        )
        if recue:
            reception = ReceptionAchat.objects.create(
                commande=commande,
                est_validee=True,
                auteur=self.administrateur,
            )
            LigneReception.objects.create(
                reception=reception,
                ligne_achat=ligne,
                quantite=recue,
                numero_lot="LOT-1",
                date_peremption=timezone.localdate() + timedelta(days=365),
            )
        return commande


class PermissionsFournisseursTests(BaseFournisseursTests):
    def test_liste_exige_une_connexion(self):
        reponse = self.client.get(reverse("fournisseurs:liste"))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn(reverse("utilisateurs:connexion"), reponse.url)

    def test_lecteur_consulte_mais_ne_cree_pas(self):
        self.client.force_login(self.lecteur)
        self.assertEqual(
            self.client.get(reverse("fournisseurs:liste")).status_code, 200
        )
        self.assertEqual(
            self.client.get(reverse("fournisseurs:creation")).status_code, 403
        )

    def test_gestionnaire_cree_et_desactive_sans_supprimer(self):
        self.client.force_login(self.gestionnaire)
        reponse = self.client.post(
            reverse("fournisseurs:creation"),
            {"nom": "Nouveau Fournisseur", "actif": "on"},
        )
        self.assertEqual(reponse.status_code, 302)
        fournisseur = Fournisseur.objects.get(nom="Nouveau Fournisseur")

        reponse = self.client.post(
            reverse("fournisseurs:desactiver", args=[fournisseur.pk])
        )
        self.assertRedirects(
            reponse, reverse("fournisseurs:detail", args=[fournisseur.pk])
        )
        fournisseur.refresh_from_db()
        self.assertFalse(fournisseur.actif)

        reponse = self.client.get(
            reverse("fournisseurs:suppression", args=[fournisseur.pk])
        )
        self.assertEqual(reponse.status_code, 403)

    def test_administrateur_supprime_sans_historique(self):
        self.client.force_login(self.administrateur)
        fournisseur = self.creer_fournisseur()
        reponse = self.client.post(
            reverse("fournisseurs:suppression", args=[fournisseur.pk])
        )
        self.assertRedirects(reponse, reverse("fournisseurs:liste"))
        self.assertFalse(
            Fournisseur.objects.filter(pk=fournisseur.pk).exists()
        )

    def test_suppression_bloquee_si_commandes(self):
        self.client.force_login(self.administrateur)
        fournisseur = self.creer_fournisseur()
        self.creer_achat(fournisseur, recue=0)
        reponse = self.client.post(
            reverse("fournisseurs:suppression", args=[fournisseur.pk]),
            follow=True,
        )
        self.assertTrue(Fournisseur.objects.filter(pk=fournisseur.pk).exists())
        self.assertContains(reponse, "ne peut pas être supprimé")


class RechercheFournisseursTests(BaseFournisseursTests):
    def setUp(self):
        self.fournisseur = self.creer_fournisseur(
            nom="Pharma Distrib", telephone="0341111111"
        )
        self.autre = self.creer_fournisseur(
            nom="MediLog", telephone="0349999999"
        )
        self.client.force_login(self.lecteur)

    def test_recherche_par_nom(self):
        reponse = self.client.get(
            reverse("fournisseurs:liste"), {"q": "pharma"}
        )
        self.assertContains(reponse, "Pharma Distrib")
        self.assertNotContains(reponse, "MediLog")

    def test_recherche_par_telephone(self):
        reponse = self.client.get(
            reverse("fournisseurs:liste"), {"q": "0349999999"}
        )
        self.assertContains(reponse, "MediLog")
        self.assertNotContains(reponse, "Pharma Distrib")

    def test_filtre_par_statut(self):
        self.autre.actif = False
        self.autre.save(update_fields=["actif"])
        reponse = self.client.get(
            reverse("fournisseurs:liste"), {"statut": "inactifs"}
        )
        self.assertContains(reponse, "MediLog")
        self.assertNotContains(reponse, "Pharma Distrib")


class DetailFournisseurTests(BaseFournisseursTests):
    def setUp(self):
        self.client.force_login(self.administrateur)
        self.fournisseur = self.creer_fournisseur()
        self.commande = self.creer_achat(
            self.fournisseur, quantite=10, prix="2.00", recue=4
        )

    def test_montants_commandes_et_receptionnes(self):
        reponse = self.client.get(
            reverse("fournisseurs:detail", args=[self.fournisseur.pk])
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.context["total_commande"], Decimal("20.00"))
        self.assertEqual(
            reponse.context["total_receptionne"], Decimal("8.00")
        )
        self.assertContains(reponse, self.commande.numero)

    def test_desactivation_conserve_lhistorique(self):
        reponse = self.client.post(
            reverse("fournisseurs:desactiver", args=[self.fournisseur.pk]),
            follow=True,
        )
        self.fournisseur.refresh_from_db()
        self.assertFalse(self.fournisseur.actif)
        self.assertTrue(
            CommandeAchat.objects.filter(pk=self.commande.pk).exists()
        )
        self.assertContains(reponse, "historique")

    def test_confirmation_avant_desactivation(self):
        reponse = self.client.get(
            reverse("fournisseurs:desactiver", args=[self.fournisseur.pk])
        )
        self.assertContains(reponse, "Désactiver")
        self.assertTrue(self.fournisseur.actif)


class PaginationFournisseursTests(BaseFournisseursTests):
    def test_pagination(self):
        for index in range(25):
            self.creer_fournisseur(nom=f"Fournisseur {index:02d}")
        self.client.force_login(self.lecteur)
        reponse = self.client.get(reverse("fournisseurs:liste"))
        self.assertTrue(reponse.context["is_paginated"])
        self.assertEqual(len(reponse.context["fournisseurs"]), 20)
