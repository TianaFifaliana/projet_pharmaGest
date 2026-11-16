from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from clients.models import Client
from fournisseurs.models import Fournisseur
from medicaments.models import Categorie, Medicament
from stock.models import LotStock
from utilisateurs.roles import ADMINISTRATEUR, CAISSIER, GESTIONNAIRE_STOCK, PHARMACIEN_RESPONSABLE


User = get_user_model()


class Command(BaseCommand):
    help = "Charge des données de démonstration (idempotent, dev/test uniquement)."

    def add_arguments(self, parser):
        parser.add_argument("--reset-demo-passwords", action="store_true", help="Réinitialise les mots de passe des comptes démo.")

    @transaction.atomic
    def handle(self, *args, **options):
        call_command("creer_groupes", verbosity=0)
        admin, _ = User.objects.get_or_create(username="admin_demo", defaults={"email": "admin@demo.local", "is_staff": True, "is_active": True})
        pharma, _ = User.objects.get_or_create(username="pharmacien_demo", defaults={"email": "pharma@demo.local", "is_active": True})
        stock_user, _ = User.objects.get_or_create(username="stock_demo", defaults={"email": "stock@demo.local", "is_active": True})
        caissier, _ = User.objects.get_or_create(username="caissier_demo", defaults={"email": "caisse@demo.local", "is_active": True})
        if options["reset_demo_passwords"] or not admin.has_usable_password():
            for u, pwd, role in [
                (admin, "AdminDemo123!", ADMINISTRATEUR),
                (pharma, "PharmaDemo123!", PHARMACIEN_RESPONSABLE),
                (stock_user, "StockDemo123!", GESTIONNAIRE_STOCK),
                (caissier, "CaisseDemo123!", CAISSIER),
            ]:
                u.set_password(pwd)
                u.save()
                u.groups.set([u.groups.model.objects.get(name=role)]) if False else None
        from django.contrib.auth.models import Group
        admin.groups.set([Group.objects.get(name=ADMINISTRATEUR)])
        pharma.groups.set([Group.objects.get(name=PHARMACIEN_RESPONSABLE)])
        stock_user.groups.set([Group.objects.get(name=GESTIONNAIRE_STOCK)])
        caissier.groups.set([Group.objects.get(name=CAISSIER)])

        cat1, _ = Categorie.objects.get_or_create(nom="Antalgiques", defaults={"description": "Douleur et fièvre"})
        cat2, _ = Categorie.objects.get_or_create(nom="Antibiotiques", defaults={"description": "Infections bactériennes"})
        cat3, _ = Categorie.objects.get_or_create(nom="Vitamines", defaults={"description": "Compléments"})
        meds = [
            ("Paracétamol 500mg", cat1, Medicament.Forme.COMPRIME, "500 mg", "500", "1500", 20),
            ("Amoxicilline 1g", cat2, Medicament.Forme.GELULE, "1 g", "1200", "2500", 15),
            ("Vitamine C 1000", cat3, Medicament.Forme.COMPRIME, "1000 mg", "300", "900", 30),
        ]
        created_meds = []
        for nom, cat, forme, dosage, pa, pv, seuil in meds:
            m, _ = Medicament.objects.get_or_create(
                nom_commercial=nom,
                defaults={"categorie": cat, "forme": forme, "dosage": dosage, "prix_achat": Decimal(pa), "prix_vente": Decimal(pv), "seuil_alerte": seuil, "statut": Medicament.Statut.ACTIF},
            )
            created_meds.append(m)
        Fournisseur.objects.get_or_create(nom="Fournisseur Démo A", defaults={"telephone": "0340000001", "actif": True})
        Fournisseur.objects.get_or_create(nom="Fournisseur Démo B", defaults={"telephone": "0340000002", "actif": True})
        Client.objects.get_or_create(nom="Rakoto", prenom="Jean", defaults={"telephone": "0320000001", "actif": True})
        Client.objects.get_or_create(nom="Rasoa", prenom="Marie", defaults={"telephone": "0320000002", "actif": True})
        today = date.today()
        for i, m in enumerate(created_meds, start=1):
            LotStock.objects.get_or_create(
                medicament=m, numero_lot=f"DEMO-LOT-{i}",
                defaults={"quantite_recue": 100, "quantite_disponible": 100, "date_peremption": today + timedelta(days=365), "date_reception": today, "bloque": False},
            )
        self.stdout.write(self.style.SUCCESS("Données de démonstration chargées. Comptes: admin_demo/AdminDemo123!, pharmacien_demo/PharmaDemo123!, stock_demo/StockDemo123!, caissier_demo/CaisseDemo123!"))
