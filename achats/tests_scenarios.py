from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from achats.models import CommandeAchat, LigneAchat, ReceptionAchat
from achats.services import changer_statut, valider_reception
from medicaments.models import Categorie, Medicament
from stock.models import LotStock, MouvementStock
from utilisateurs.models import User
from utilisateurs.roles import GESTIONNAIRE_STOCK


def make_user(username, role=None, password="MotDePasse123!"):
    user = User.objects.create_user(username, password=password)
    if role:
        user.groups.add(Group.objects.get(name=role))
    return user


def make_medicament(nom="Para", prix_vente="200.00"):
    cat = Categorie.objects.create(nom=f"Cat-{nom}")
    return Medicament.objects.create(
        nom_commercial=nom,
        categorie=cat,
        prix_achat=Decimal("100.00"),
        prix_vente=Decimal(prix_vente),
        statut=Medicament.Statut.ACTIF,
    )


def make_commande_validee(auteur, medicament, quantite=20):
    from fournisseurs.models import Fournisseur

    f = Fournisseur.objects.create(nom="Fournisseur A")
    cmd = CommandeAchat.objects.create(fournisseur=f, auteur=auteur, statut=CommandeAchat.Statut.BROUILLON)
    ligne = LigneAchat.objects.create(commande=cmd, medicament=medicament, quantite=quantite, prix_unitaire=Decimal("100.00"))
    changer_statut(cmd, CommandeAchat.Statut.COMMANDEE, utilisateur=auteur)
    return cmd, ligne


class ReceptionStockTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("creer_groupes", stdout=StringIO())

    def setUp(self):
        self.user = make_user("gesta", GESTIONNAIRE_STOCK)
        self.med = make_medicament("MedRecep")
        self.cmd, self.ligne = make_commande_validee(self.user, self.med, quantite=20)

    def test_4_reception_20_unites_une_seule_fois(self):
        reception = ReceptionAchat.objects.create(commande=self.cmd, auteur=self.user)
        data = [{
            "ligne_achat": self.ligne,
            "quantite": 20,
            "numero_lot": "LOT-20",
            "date_peremption": timezone.localdate() + timedelta(days=365),
        }]
        valider_reception(reception, data, utilisateur=self.user)
        lot = LotStock.objects.get(medicament=self.med, numero_lot="LOT-20")
        self.assertEqual(lot.quantite_recue, 20)
        self.assertEqual(lot.quantite_disponible, 20)
        self.assertEqual(MouvementStock.objects.filter(lot=lot, type_mouvement=MouvementStock.TypeMouvement.ENTREE).count(), 1)
        self.assertEqual(sum(m.quantite for m in MouvementStock.objects.filter(lot=lot, type_mouvement=MouvementStock.TypeMouvement.ENTREE)), 20)

        # rejouer la validation : pas de doublon
        with self.assertRaises(ValidationError):
            valider_reception(reception, data, utilisateur=self.user)
        lot.refresh_from_db()
        self.assertEqual(lot.quantite_recue, 20)
        self.assertEqual(lot.quantite_disponible, 20)
        self.assertEqual(MouvementStock.objects.filter(lot=lot, type_mouvement=MouvementStock.TypeMouvement.ENTREE).count(), 1)

    def test_10_double_validation_reception_pas_de_doublon(self):
        reception = ReceptionAchat.objects.create(commande=self.cmd, auteur=self.user)
        data = [{
            "ligne_achat": self.ligne,
            "quantite": 20,
            "numero_lot": "LOT-X",
            "date_peremption": timezone.localdate() + timedelta(days=365),
        }]
        valider_reception(reception, data, utilisateur=self.user)
        # seconde tentative (validation "simultanée"/répétée) refusée sans effet de bord
        with self.assertRaises(ValidationError):
            valider_reception(reception, data, utilisateur=self.user)
        lot = LotStock.objects.get(medicament=self.med, numero_lot="LOT-X")
        self.assertEqual(lot.quantite_disponible, 20)
        self.assertFalse(lot.quantite_disponible < 0)
