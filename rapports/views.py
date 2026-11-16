import json
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone
from django.views.generic import TemplateView

from achats.models import ReceptionAchat
from medicaments.models import Medicament
from stock.models import LotStock
from stock.services import DEFAULT_JOURS_ALERTE_PEREMPTION
from utilisateurs.mixins import ConnexionRequiseMixin
from utilisateurs.roles import ADMINISTRATEUR, CAISSIER, PHARMACIEN_RESPONSABLE, RESPONSABLE_GESTION
from ventes.models import LigneVente, Paiement, Vente

from .forms import PeriodeDashboardForm


class TableauBordView(ConnexionRequiseMixin, TemplateView):
    template_name = "rapports/tableau_bord.html"

    def _scope_ventes_propres(self, user):
        return bool(
            user.a_un_role(CAISSIER)
            and not (
                user.is_superuser
                or user.a_un_role(RESPONSABLE_GESTION, PHARMACIEN_RESPONSABLE, ADMINISTRATEUR)
            )
        )

    def get(self, request, *args, **kwargs):
        self.form = PeriodeDashboardForm(request.GET or None)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.localdate()
        debut_defaut = today.replace(day=1)
        fin_defaut = today

        if self.form.is_valid():
            date_debut = self.form.cleaned_data.get("date_debut") or debut_defaut
            date_fin = self.form.cleaned_data.get("date_fin") or fin_defaut
        else:
            date_debut, date_fin = debut_defaut, fin_defaut

        scope_propres = self._scope_ventes_propres(user)
        voir_stats_globales = bool(
            user.is_superuser
            or user.a_un_role(RESPONSABLE_GESTION, PHARMACIEN_RESPONSABLE, ADMINISTRATEUR)
        )

        ventes_base = Vente.objects.filter(statut=Vente.Statut.VALIDEE)
        if scope_propres:
            ventes_base = ventes_base.filter(auteur=user)

        ventes_jour = ventes_base.filter(date_validation__date=today)
        ca_jour = ventes_jour.aggregate(
            total=Coalesce(Sum(F("lignes__quantite") * F("lignes__prix_applique")), Value(Decimal("0.00")), output_field=DecimalField(max_digits=14, decimal_places=2))
        )["total"]

        ventes_periode = ventes_base.filter(date_validation__date__gte=date_debut, date_validation__date__lte=date_fin)
        lignes_periode = LigneVente.objects.filter(vente__in=ventes_periode)

        ca_periode = lignes_periode.aggregate(
            total=Coalesce(Sum(F("quantite") * F("prix_applique")), Value(Decimal("0.00")), output_field=DecimalField(max_digits=14, decimal_places=2))
        )["total"]
        cout_periode = lignes_periode.aggregate(
            total=Coalesce(Sum(F("quantite") * F("lot__medicament__prix_achat")), Value(Decimal("0.00")), output_field=DecimalField(max_digits=14, decimal_places=2))
        )["total"]
        marge_commerciale = (ca_periode or Decimal("0.00")) - (cout_periode or Decimal("0.00"))

        encaissements_qs = Paiement.objects.filter(
            statut=Paiement.Statut.VALIDE,
            date_paiement__date__gte=date_debut,
            date_paiement__date__lte=date_fin,
            vente__statut=Vente.Statut.VALIDEE,
        )
        if scope_propres:
            encaissements_qs = encaissements_qs.filter(vente__auteur=user)
        encaissements_periode = encaissements_qs.aggregate(
            total=Coalesce(Sum("montant"), Value(Decimal("0.00")), output_field=DecimalField(max_digits=14, decimal_places=2))
        )["total"]

        # Cartes stock/médicaments (ORM)
        medicaments_actifs = Medicament.objects.filter(statut=Medicament.Statut.ACTIF).count()
        jours_peremption = DEFAULT_JOURS_ALERTE_PEREMPTION
        limite = today + timedelta(days=jours_peremption)

        stock_valide_sq = (
            LotStock.objects.filter(
                medicament=OuterRef("pk"),
                bloque=False,
                date_peremption__gte=today,
                quantite_disponible__gt=0,
            )
            .values("medicament")
            .annotate(total=Sum("quantite_disponible"))
            .values("total")[:1]
        )
        meds_avec_stock = Medicament.objects.filter(statut=Medicament.Statut.ACTIF).annotate(
            stock_valide=Coalesce(Subquery(stock_valide_sq, output_field=DecimalField(max_digits=12, decimal_places=0)), Value(0))
        )
        stocks_faibles = meds_avec_stock.filter(stock_valide__lt=F("seuil_alerte")).count()
        peremptions_proches = LotStock.objects.filter(
            date_peremption__gte=today, date_peremption__lte=limite, quantite_disponible__gt=0, bloque=False
        ).count()
        lots_perimes_count = LotStock.objects.filter(date_peremption__lt=today, quantite_disponible__gt=0).count()

        # Achats sur période (réceptions validées) - stats globales
        achats_periode = Decimal("0.00")
        if voir_stats_globales or not scope_propres:
            achats_periode = (
                ReceptionAchat.objects.filter(
                    est_validee=True,
                    date_validation__date__gte=date_debut,
                    date_validation__date__lte=date_fin,
                )
                .aggregate(total=Coalesce(Sum(F("lignes__quantite") * F("lignes__ligne_achat__prix_unitaire")), Value(Decimal("0.00")), output_field=DecimalField(max_digits=14, decimal_places=2)))
            )["total"]

        # Top produits vendus
        top_produits_qs = (
            lignes_periode.values("lot__medicament__nom_commercial", "lot__medicament_id")
            .annotate(
                quantite_vendue=Coalesce(Sum("quantite"), 0),
                montant_vendu=Coalesce(Sum(F("quantite") * F("prix_applique")), Value(Decimal("0.00")), output_field=DecimalField(max_digits=14, decimal_places=2)),
            )
            .order_by("-quantite_vendue")[:10]
        )
        top_produits = list(top_produits_qs)

        # Alertes / lots
        lots_perimes = (
            LotStock.objects.select_related("medicament")
            .filter(date_peremption__lt=today, quantite_disponible__gt=0)
            .order_by("date_peremption")[:10]
        )
        lots_proches = (
            LotStock.objects.select_related("medicament")
            .filter(date_peremption__gte=today, date_peremption__lte=limite, quantite_disponible__gt=0, bloque=False)
            .order_by("date_peremption")[:10]
        )
        alertes_stock = (
            meds_avec_stock.filter(stock_valide__lt=F("seuil_alerte"))
            .order_by("stock_valide", "nom_commercial")[:10]
        )

        # Charts data
        ventes_cat = (
            lignes_periode.values("lot__medicament__categorie__nom")
            .annotate(montant=Coalesce(Sum(F("quantite") * F("prix_applique")), Value(Decimal("0.00")), output_field=DecimalField(max_digits=14, decimal_places=2)))
            .order_by("-montant")
        )
        cat_labels = [v["lot__medicament__categorie__nom"] or "Sans catégorie" for v in ventes_cat]
        cat_values = [float(v["montant"] or 0) for v in ventes_cat]

        top_labels = [p["lot__medicament__nom_commercial"] for p in top_produits]
        top_values = [int(p["quantite_vendue"] or 0) for p in top_produits]

        debut_mois = (today.replace(day=1) - timedelta(days=365)).replace(day=1)
        ventes_mensuelles_qs = (
            Vente.objects.filter(statut=Vente.Statut.VALIDEE, date_validation__date__gte=debut_mois)
        )
        if scope_propres:
            ventes_mensuelles_qs = ventes_mensuelles_qs.filter(auteur=user)
        ventes_mensuelles = (
            LigneVente.objects.filter(vente__in=ventes_mensuelles_qs)
            .annotate(mois=TruncMonth("vente__date_validation"))
            .values("mois")
            .annotate(montant=Coalesce(Sum(F("quantite") * F("prix_applique")), Value(Decimal("0.00")), output_field=DecimalField(max_digits=14, decimal_places=2)))
            .order_by("mois")
        )
        mois_labels = [v["mois"].strftime("%m/%Y") for v in ventes_mensuelles if v["mois"]]
        mois_values = [float(v["montant"] or 0) for v in ventes_mensuelles if v["mois"]]

        ctx.update(
            {
                "form": self.form,
                "date_debut": date_debut,
                "date_fin": date_fin,
                "scope_propres": scope_propres,
                "voir_stats_globales": voir_stats_globales,
                "medicaments_actifs": medicaments_actifs,
                "ca_jour": ca_jour or Decimal("0.00"),
                "stocks_faibles": stocks_faibles,
                "peremptions_proches": peremptions_proches,
                "lots_perimes_count": lots_perimes_count,
                "ca_periode": ca_periode or Decimal("0.00"),
                "encaissements_periode": encaissements_periode or Decimal("0.00"),
                "marge_commerciale": marge_commerciale,
                "achats_periode": achats_periode or Decimal("0.00"),
                "top_produits": top_produits,
                "lots_perimes": lots_perimes,
                "lots_proches": lots_proches,
                "alertes_stock": alertes_stock,
                "chart_cat_labels": json.dumps(cat_labels),
                "chart_cat_values": json.dumps(cat_values),
                "chart_top_labels": json.dumps(top_labels),
                "chart_top_values": json.dumps(top_values),
                "chart_mois_labels": json.dumps(mois_labels),
                "chart_mois_values": json.dumps(mois_values),
            }
        )
        return ctx
