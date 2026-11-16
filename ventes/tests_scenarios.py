import json
import threading
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from medicaments.models import Categorie, Medicament
from stock.models import LotStock, MouvementStock
from utilisateurs.models import User
from utilisateurs.roles import CAISSIER
from ventes.models import Paiement, Vente
from ventes.services import confirmer_vente


def make_user(username, role=None, password="MotDePasse123!"):
    from django.contrib.auth.models import Group
    user = User.objects.create_user(username, password=password)
    if role:
        user.groups.add(Group.objects.get(name=role))
    return user


def make_lot(qte=10, perime=False, bloque=False, prix_vente="200.00"):
    cat = Categorie.objects.create(nom=f"Cat{Categorie.objects.count()+1}")
    med = Medicament.objects.create(
        nom_commercial=f"Med{Medicament.objects.count()+1}",
        categorie=cat,
        prix_achat=Decimal("100.00"),
        prix_vente=Decimal(prix_vente),
        statut=Medicament.Statut.ACTIF,
    )
    date_peremption = timezone.localdate() - timedelta(days=1) if perime else timezone.localdate() + timedelta(days=365)
    return LotStock.objects.create(
        medicament=med,
        numero_lot=f"LOT{LotStock.objects.count()+1}",
        date_peremption=date_peremption,
        quantite_recue=qte,
        quantite_disponible=qte,
        bloque=bloque,
    )


class VenteStockTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("creer_groupes", stdout=StringIO())

    def setUp(self):
        self.user = make_user("caissv", CAISSIER)

    def _payload(self, lot, qte):
        return json.dumps([{"lot_id": lot.pk, "quantite": qte}])

    def test_5_vendre_3_unites_stock_moins_3_une_seule_fois(self):
        lot = make_lot(qte=10)
        vente = confirmer_vente(
            lignes_payload=self._payload(lot, 3),
            mode_paiement=Paiement.Mode.ESPECES,
            utilisateur=self.user,
        )
        lot.refresh_from_db()
        self.assertEqual(lot.quantite_disponible, 7)
        self.assertEqual(MouvementStock.objects.filter(lot=lot, type_mouvement=MouvementStock.TypeMouvement.SORTIE).count(), 1)
        mv = MouvementStock.objects.get(lot=lot, type_mouvement=MouvementStock.TypeMouvement.SORTIE)
        self.assertEqual(mv.quantite, 3)
        self.assertEqual(vente.statut, Vente.Statut.VALIDEE)

    def test_6_vendre_plus_que_stock_refuse(self):
        lot = make_lot(qte=2)
        with self.assertRaises(ValidationError):
            confirmer_vente(
                lignes_payload=self._payload(lot, 5),
                mode_paiement=Paiement.Mode.ESPECES,
                utilisateur=self.user,
            )
        lot.refresh_from_db()
        self.assertEqual(lot.quantite_disponible, 2)
        self.assertEqual(Vente.objects.count(), 0)
        self.assertEqual(MouvementStock.objects.filter(lot=lot, type_mouvement=MouvementStock.TypeMouvement.SORTIE).count(), 0)

    def test_7_vendre_lot_perime_refuse(self):
        lot = make_lot(qte=5, perime=True)
        with self.assertRaises(ValidationError):
            confirmer_vente(
                lignes_payload=self._payload(lot, 1),
                mode_paiement=Paiement.Mode.ESPECES,
                utilisateur=self.user,
            )
        lot.refresh_from_db()
        self.assertEqual(lot.quantite_disponible, 5)
        self.assertEqual(Vente.objects.count(), 0)

    def test_8_acces_sans_permission_caisse_403(self):
        from utilisateurs.roles import GESTIONNAIRE_STOCK
        gest = make_user("gestv", GESTIONNAIRE_STOCK)
        self.client.force_login(gest)
        resp = self.client.get("/ventes/caisse/")
        self.assertEqual(resp.status_code, 403)


class VenteConcurrenteTests(TransactionTestCase):
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("creer_groupes", stdout=StringIO())

    def setUp(self):
        self.user = make_user("caissc", CAISSIER)

    def _payload(self, lot, qte):
        return json.dumps([{"lot_id": lot.pk, "quantite": qte}])

    def test_10_deux_validations_simultanees_pas_double_sortie_ni_stock_negatif(self):
        if connection.vendor == "sqlite":
            self.skipTest("Concurrence réelle non fiable sur SQLite ; le garde-fou atomique est couvert par le test séquentiel.")
        lot = make_lot(qte=3)
        results = []
        errors = []

        def vendre():
            try:
                confirmer_vente(
                    lignes_payload=self._payload(lot, 3),
                    mode_paiement=Paiement.Mode.ESPECES,
                    utilisateur=self.user,
                )
                results.append("ok")
            except Exception as e:
                errors.append(e)
            finally:
                connection.close()

        t1 = threading.Thread(target=vendre)
        t2 = threading.Thread(target=vendre)
        t1.start(); t2.start(); t1.join(); t2.join()

        lot.refresh_from_db()
        self.assertEqual(len(results), 1)
        self.assertEqual(len(errors), 1)
        self.assertEqual(lot.quantite_disponible, 0)
        self.assertFalse(lot.quantite_disponible < 0)
        self.assertEqual(MouvementStock.objects.filter(lot=lot, type_mouvement=MouvementStock.TypeMouvement.SORTIE).count(), 1)


class VenteDoubleValidationGardeFouTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("creer_groupes", stdout=StringIO())

    def setUp(self):
        self.user = make_user("caissd", CAISSIER)

    def test_10_seconde_validation_refusee_sans_double_sortie_ni_stock_negatif(self):
        lot = make_lot(qte=3)
        payload = json.dumps([{"lot_id": lot.pk, "quantite": 3}])
        confirmer_vente(lignes_payload=payload, mode_paiement=Paiement.Mode.ESPECES, utilisateur=self.user)
        with self.assertRaises(ValidationError):
            confirmer_vente(lignes_payload=payload, mode_paiement=Paiement.Mode.ESPECES, utilisateur=self.user)
        lot.refresh_from_db()
        self.assertEqual(lot.quantite_disponible, 0)
        self.assertFalse(lot.quantite_disponible < 0)
        self.assertEqual(MouvementStock.objects.filter(lot=lot, type_mouvement=MouvementStock.TypeMouvement.SORTIE).count(), 1)
