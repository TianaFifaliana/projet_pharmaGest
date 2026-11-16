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
from utilisateurs.roles import CAISSIER
from ventes.models import Paiement, Vente, LigneVente


def make_user(username, role=None, password="MotDePasse123!"):
    user = User.objects.create_user(username, password=password)
    if role:
        user.groups.add(Group.objects.get(name=role))
    return user


def make_vente_validee(auteur):
    cat = Categorie.objects.create(nom="CatPDF")
    med = Medicament.objects.create(nom_commercial="MedPDF", categorie=cat, prix_achat=Decimal("50.00"), prix_vente=Decimal("120.00"))
    lot = LotStock.objects.create(medicament=med, numero_lot="LPDF", date_peremption=timezone.localdate().replace(year=timezone.localdate().year+1), quantite_recue=10, quantite_disponible=7, bloque=False)
    vente = Vente.objects.create(auteur=auteur, statut=Vente.Statut.VALIDEE, date_validation=timezone.now())
    LigneVente.objects.create(vente=vente, lot=lot, quantite=3, prix_applique=Decimal("120.00"))
    Paiement.objects.create(vente=vente, mode=Paiement.Mode.ESPECES, statut=Paiement.Statut.VALIDE, montant=Decimal("360.00"), auteur=auteur)
    return vente


class PdfRapportsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("creer_groupes", stdout=StringIO())

    def setUp(self):
        self.caissier = make_user("caisspdf", CAISSIER)

    def test_9_recu_pdf_genere_avec_bons_totaux(self):
        from rapports.pdf import format_mga, pdf_recu_vente

        vente = make_vente_validee(self.caissier)
        self.assertEqual(vente.montant_total, Decimal("360.00"))
        self.client.force_login(self.caissier)
        url = reverse("rapports:pdf_recu_vente", args=[vente.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertTrue(resp.content.startswith(b"%PDF"))
        self.assertGreater(len(resp.content), 800)
        # génération directe et cohérence des totaux figés
        buf = pdf_recu_vente(vente)
        self.assertTrue(buf.getvalue().startswith(b"%PDF"))
        self.assertEqual(format_mga(vente.montant_total), "360,00 MGA")

    def test_8_acces_pdf_sans_permission_403(self):
        # utilisateur sans perm ventes view
        other = make_user("noperm")
        vente = make_vente_validee(self.caissier)
        self.client.force_login(other)
        resp = self.client.get(reverse("rapports:pdf_recu_vente", args=[vente.pk]))
        self.assertEqual(resp.status_code, 403)
