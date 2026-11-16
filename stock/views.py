from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from medicaments.models import Medicament
from utilisateurs.mixins import PermissionRequiseMixin, permission_requise
from utilisateurs.roles import PHARMACIEN_RESPONSABLE

from .forms import AlertePeremptionForm, FiltreMouvementStockForm, InventaireLotForm
from .models import LotStock, MouvementStock
from .services import (
    DEFAULT_JOURS_ALERTE_PEREMPTION,
    appliquer_correction_inventaire,
    calculer_alertes,
    changer_blocage_lot,
    est_pharmacien_responsable,
    stock_valide_medicament,
)


class VueStockDisponibleView(PermissionRequiseMixin, ListView):
    """Stock disponible par médicament (somme des lots valides) et par lot."""

    model = Medicament
    template_name = "stock/disponible.html"
    context_object_name = "medicaments"
    permission_required = "stock.view_lotstock"
    paginate_by = 25

    def get_queryset(self):
        aujourd_hui = timezone.localdate()
        qs = Medicament.objects.filter(statut=Medicament.Statut.ACTIF).annotate(
            stock_valide=Sum(
                "lots__quantite_disponible",
                filter=Q(
                    lots__bloque=False,
                    lots__date_peremption__gte=aujourd_hui,
                    lots__quantite_disponible__gt=0,
                ),
            )
        )
        recherche = self.request.GET.get("q", "").strip()
        if recherche:
            qs = qs.filter(
                Q(nom_commercial__icontains=recherche)
                | Q(nom_generique__icontains=recherche)
                | Q(code_barres__icontains=recherche)
            )
        etat = self.request.GET.get("etat", "").strip()
        if etat == "rupture":
            qs = qs.filter(Q(stock_valide__isnull=True) | Q(stock_valide__lte=0))
        elif etat == "alerte":
            qs = qs.filter(stock_valide__gt=0, stock_valide__lt=F("seuil_alerte"))
        elif etat == "ok":
            qs = qs.filter(stock_valide__gte=F("seuil_alerte"))
        return qs.order_by("nom_commercial")

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        aujourd_hui = timezone.localdate()
        lots = (
            LotStock.objects.select_related("medicament", "medicament__categorie")
            .order_by("medicament__nom_commercial", "date_peremption", "numero_lot")
        )
        med_id = self.request.GET.get("medicament", "").strip()
        if med_id.isdigit():
            lots = lots.filter(medicament_id=med_id)
        contexte.update(
            {
                "lots": lots,
                "aujourd_hui": aujourd_hui,
                "recherche": self.request.GET.get("q", ""),
                "etat_filtre": self.request.GET.get("etat", ""),
                "medicament_filtre": self.request.GET.get("medicament", ""),
                "medicaments_filtre": Medicament.objects.filter(
                    statut=Medicament.Statut.ACTIF
                ).order_by("nom_commercial"),
            }
        )
        return contexte


class HistoriqueMouvementsView(PermissionRequiseMixin, ListView):
    model = MouvementStock
    template_name = "stock/mouvements.html"
    context_object_name = "mouvements"
    permission_required = "stock.view_mouvementstock"
    paginate_by = 30

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("lot", "lot__medicament", "auteur")
            .order_by("-date_mouvement", "-pk")
        )
        form = FiltreMouvementStockForm(self.request.GET or None)
        self.filtre_form = form
        if form.is_valid():
            if form.cleaned_data.get("medicament"):
                qs = qs.filter(lot__medicament=form.cleaned_data["medicament"])
            if form.cleaned_data.get("type_mouvement"):
                qs = qs.filter(type_mouvement=form.cleaned_data["type_mouvement"])
            if form.cleaned_data.get("date_debut"):
                qs = qs.filter(date_mouvement__date__gte=form.cleaned_data["date_debut"])
            if form.cleaned_data.get("date_fin"):
                qs = qs.filter(date_mouvement__date__lte=form.cleaned_data["date_fin"])
            if form.cleaned_data.get("utilisateur"):
                qs = qs.filter(auteur=form.cleaned_data["utilisateur"])
        return qs

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["form_filtre"] = getattr(self, "filtre_form", FiltreMouvementStockForm())
        return contexte


class AlertesStockView(PermissionRequiseMixin, View):
    permission_required = "stock.view_lotstock"
    template_name = "stock/alertes.html"

    def get(self, request):
        form = AlertePeremptionForm(request.GET or None)
        jours = DEFAULT_JOURS_ALERTE_PEREMPTION
        if form.is_valid():
            jours = form.cleaned_data["jours"]
        else:
            form = AlertePeremptionForm(initial={"jours": jours})
        alertes = calculer_alertes(jours_peremption=jours)
        contexte = {"form": form, **alertes}
        return render(request, self.template_name, contexte)


class InventairePhysiqueView(PermissionRequiseMixin, View):
    """Saisie du stock compté, calcul de l'écart, correction -> MouvementStock correction."""

    permission_required = "stock.change_lotstock"
    template_name = "stock/inventaire.html"

    def _lots(self):
        return LotStock.objects.select_related("medicament").order_by(
            "medicament__nom_commercial", "date_peremption", "numero_lot"
        )

    def get(self, request):
        lot_id = request.GET.get("lot", "").strip()
        lot = get_object_or_404(LotStock, pk=lot_id) if lot_id.isdigit() else None
        form = InventaireLotForm()
        return render(request, self.template_name, self._contexte(lot, form))

    def post(self, request):
        lot_id = request.POST.get("lot") or request.GET.get("lot")
        if not lot_id or not str(lot_id).isdigit():
            messages.error(request, "Sélectionnez un lot à inventorier.")
            return redirect("stock:inventaire")
        lot = get_object_or_404(LotStock, pk=lot_id)
        form = InventaireLotForm(request.POST)
        if form.is_valid():
            try:
                mouvement, ecart = appliquer_correction_inventaire(
                    lot,
                    form.cleaned_data["stock_compte"],
                    form.cleaned_data["motif"],
                    request.user,
                    request=request,
                )
            except (ValidationError, PermissionDenied) as e:
                msgs = e.messages if hasattr(e, "messages") else [str(e)]
                for m in msgs:
                    form.add_error(None, m)
            else:
                messages.success(
                    request,
                    f"Correction enregistrée (écart {ecart:+d}). Mouvement #{mouvement.pk} créé.",
                )
                return redirect("stock:inventaire")
        return render(request, self.template_name, self._contexte(lot, form))

    def _contexte(self, lot, form):
        stock_compte = None
        ecart = None
        if lot and self.request.method == "POST":
            raw = self.request.POST.get("stock_compte")
            if raw not in (None, ""):
                try:
                    stock_compte = int(raw)
                    ecart = stock_compte - lot.quantite_disponible
                except (TypeError, ValueError):
                    pass
        return {
            "form": form,
            "lot": lot,
            "lots": self._lots(),
            "ecart": ecart,
            "stock_compte_preview": stock_compte,
        }


class BasculerBlocageLotView(PermissionRequiseMixin, View):
    permission_required = "stock.change_lotstock"

    def post(self, request, pk):
        if not est_pharmacien_responsable(request.user):
            raise PermissionDenied("Action réservée au pharmacien responsable.")
        lot = get_object_or_404(LotStock.objects.select_related("medicament"), pk=pk)
        cible = not lot.bloque
        try:
            changer_blocage_lot(lot, cible, request.user, request=request)
        except (ValidationError, PermissionDenied) as e:
            msgs = e.messages if hasattr(e, "messages") else [str(e)]
            for m in msgs:
                messages.error(request, m)
        else:
            messages.success(
                request,
                f"Le lot {lot.numero_lot} a été {'bloqué' if cible else 'débloqué'}.",
            )
        next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse("stock:disponible")
        return redirect(next_url)
