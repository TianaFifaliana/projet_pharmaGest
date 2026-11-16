from decimal import Decimal
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from medicaments.forms import FormulaireMedicament
from medicaments.models import Categorie, Medicament
from stock.models import LotStock
from stock.services import calculer_alertes, stock_valide_medicament


class StockCalculsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("creer_groupes", stdout=StringIO())

    def test_calcul_stock_valide_et_alertes(self):
        cat = Categorie.objects.create(nom="CalcCat")
        med = Medicament.objects.create(nom_commercial="MedCalc", categorie=cat, prix_achat=Decimal("10"), prix_vente=Decimal("20"), seuil_alerte=5)
        LotStock.objects.create(medicament=med, numero_lot="A", date_peremption=timezone.localdate().replace(year=timezone.localdate().year+1), quantite_recue=3, quantite_disponible=3)
        LotStock.objects.create(medicament=med, numero_lot="B", date_peremption=timezone.localdate().replace(year=timezone.localdate().year+1), quantite_recue=2, quantite_disponible=2, bloque=True)
        # seul lot A est valide
        self.assertEqual(stock_valide_medicament(med.pk), 3)
        alertes = calculer_alertes(jours_peremption=30)
        self.assertTrue(any(m.pk == med.pk for m in alertes["sous_seuil"]))

    def test_formulaire_prix_positifs(self):
        cat = Categorie.objects.create(nom="FormCat")
        form = FormulaireMedicament(data={
            "nom_commercial": "X",
            "nom_generique": "",
            "categorie": cat.pk,
            "forme": Medicament.Forme.COMPRIME,
            "dosage": "",
            "laboratoire": "",
            "code_barres": "",
            "prix_achat": "0",
            "prix_vente": "-1",
            "seuil_alerte": "1",
            "statut": Medicament.Statut.ACTIF,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("prix_achat", form.errors)
        self.assertIn("prix_vente", form.errors)

    def test_modele_contraintes_quantite(self):
        cat = Categorie.objects.create(nom="LotCat")
        med = Medicament.objects.create(nom_commercial="MedLot", categorie=cat, prix_achat=Decimal("10"), prix_vente=Decimal("20"))
        # quantite_disponible <= quantite_recue contrainte DB - Django full_clean/DB
        lot = LotStock(medicament=med, numero_lot="Z", date_peremption=timezone.localdate(), quantite_recue=1, quantite_disponible=5)
        with self.assertRaises(Exception):
            lot.save()
