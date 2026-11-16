import uuid

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from medicaments.models import Medicament
from stock.services import get_lots_fefo
from utilisateurs.mixins import ConnexionRequiseMixin, PermissionRequiseMixin
from utilisateurs.roles import ADMINISTRATEUR, PHARMACIEN_RESPONSABLE

from .forms import AnnulationVenteForm, CaisseVenteForm, FiltreVenteForm, RetourLigneForm
from .models import LigneVente, Vente
from .services import annuler_vente, confirmer_vente, enregistrer_retour_ligne


VENTE_TOKEN_SESSION_KEY = "vente_caisse_token"


class CaisseVenteView(PermissionRequiseMixin, View):
    permission_required = "ventes.add_vente"
    template_name = "ventes/caisse.html"

    def _nouveau_token(self, request):
        token = uuid.uuid4().hex
        request.session[VENTE_TOKEN_SESSION_KEY] = token
        return token

    def get(self, request):
        form = CaisseVenteForm()
        token = self._nouveau_token(request)
        return render(request, self.template_name, {"form": form, "vente_token": token})

    def post(self, request):
        form = CaisseVenteForm(request.POST)
        token_post = request.POST.get("vente_token", "")
        if form.is_valid():
            try:
                with transaction.atomic():
                    token_session = request.session.get(VENTE_TOKEN_SESSION_KEY)
                    if not token_post or not token_session or token_post != token_session:
                        raise ValidationError("Session de vente invalide ou déjà soumise (double validation). Rechargez la caisse.")
                    # consommer le token (anti double validation)
                    request.session.pop(VENTE_TOKEN_SESSION_KEY, None)
                    vente = confirmer_vente(
                        lignes_payload=form.cleaned_data["lignes_json"],
                        mode_paiement=form.cleaned_data["mode_paiement"],
                        client=form.cleaned_data.get("client"),
                        commentaire=form.cleaned_data.get("commentaire") or "",
                        utilisateur=request.user,
                        request=request,
                    )
            except ValidationError as e:
                msgs = e.messages if hasattr(e, "messages") else [str(e)]
                for m in msgs:
                    form.add_error(None, m)
                # régénérer un token pour permettre une nouvelle tentative
                token = self._nouveau_token(request)
            else:
                messages.success(request, f"Vente {vente.numero} validée avec succès.")
                return redirect("ventes:recu", pk=vente.pk)
        else:
            token = self._nouveau_token(request)
        token = locals().get("token") or self._nouveau_token(request)
        return render(request, self.template_name, {"form": form, "vente_token": token})


class RechercheMedicamentsView(PermissionRequiseMixin, View):
    permission_required = "ventes.add_vente"

    def get(self, request):
        q = (request.GET.get("q") or "").strip()
        if not q:
            return JsonResponse({"results": []})
        from django.db.models import Q
        qs = (
            Medicament.objects.filter(statut=Medicament.Statut.ACTIF)
            .filter(
                Q(nom_commercial__icontains=q)
                | Q(nom_generique__icontains=q)
                | Q(code_barres__iexact=q)
                | Q(code_barres__icontains=q)
            )
            .order_by("nom_commercial")[:20]
        )
        results = []
        for med in qs:
            results.append(
                {
                    "id": med.id,
                    "label": str(med),
                    "nom": med.nom_commercial,
                    "prix_vente": str(med.prix_vente),
                    "code_barres": med.code_barres or "",
                }
            )
        return JsonResponse({"results": results})


class LotsMedicamentsView(PermissionRequiseMixin, View):
    permission_required = "ventes.add_vente"

    def get(self, request, medicament_id):
        med = get_object_or_404(Medicament, pk=medicament_id, statut=Medicament.Statut.ACTIF)
        lots = get_lots_fefo(med)
        results = [
            {
                "id": lot.id,
                "label": f"Lot {lot.numero_lot} (exp. {lot.date_peremption:%d/%m/%Y}) - dispo {lot.quantite_disponible}",
                "numero_lot": lot.numero_lot,
                "date_peremption": lot.date_peremption.isoformat(),
                "quantite_disponible": lot.quantite_disponible,
            }
            for lot in lots
        ]
        return JsonResponse({"medicament": {"id": med.id, "label": str(med), "prix_vente": str(med.prix_vente)}, "lots": results})


class ListeVentesView(PermissionRequiseMixin, ListView):
    model = Vente
    template_name = "ventes/liste.html"
    context_object_name = "ventes"
    permission_required = "ventes.view_vente"
    paginate_by = 20

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("client", "auteur")
            .prefetch_related("lignes", "paiements")
        )
        form = FiltreVenteForm(self.request.GET or None)
        self.filtre_form = form
        if form.is_valid():
            q = (form.cleaned_data.get("q") or "").strip()
            if q:
                qs = qs.filter(numero__icontains=q)
            if form.cleaned_data.get("statut"):
                qs = qs.filter(statut=form.cleaned_data["statut"])
            if form.cleaned_data.get("date_debut"):
                qs = qs.filter(date_creation__date__gte=form.cleaned_data["date_debut"])
            if form.cleaned_data.get("date_fin"):
                qs = qs.filter(date_creation__date__lte=form.cleaned_data["date_fin"])
            if form.cleaned_data.get("client"):
                qs = qs.filter(client=form.cleaned_data["client"])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form_filtre"] = getattr(self, "filtre_form", FiltreVenteForm())
        return ctx


class DetailVenteView(PermissionRequiseMixin, DetailView):
    model = Vente
    template_name = "ventes/detail.html"
    context_object_name = "vente"
    permission_required = "ventes.view_vente"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("client", "auteur")
            .prefetch_related(
                "lignes__lot__medicament",
                "lignes__retours",
                "paiements",
                "retours__lot",
                "retours__auteur",
                "retours__ligne_vente",
            )
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["peut_gerer_retours"] = bool(
            user.is_superuser or user.a_un_role(PHARMACIEN_RESPONSABLE, ADMINISTRATEUR)
        )
        deja_retours = self.object.retours.exists()
        ctx["peut_annuler"] = (
            ctx["peut_gerer_retours"]
            and self.object.statut == Vente.Statut.VALIDEE
            and not deja_retours
        )
        lignes = []
        for ligne in self.object.lignes.all():
            retournee = sum(r.quantite for r in ligne.retours.all())
            ligne.qte_retournee_calc = retournee
            ligne.qte_retournable_calc = max(0, ligne.quantite - retournee)
            lignes.append(ligne)
        ctx["lignes_detail"] = lignes
        return ctx


class RetourLigneView(ConnexionRequiseMixin, View):
    template_name = "ventes/retour_formulaire.html"

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or request.user.a_un_role(PHARMACIEN_RESPONSABLE, ADMINISTRATEUR)):
            raise PermissionDenied("Action réservée au pharmacien responsable ou à l'administrateur.")
        self.ligne = get_object_or_404(
            LigneVente.objects.select_related("vente", "lot", "lot__medicament"),
            pk=kwargs["ligne_id"],
            vente_id=kwargs["pk"],
        )
        self.vente = self.ligne.vente
        retournee = self.ligne.retours.aggregate(total=Sum("quantite"))["total"] or 0
        self.ligne._qte_retournee = retournee
        self.ligne._qte_retournable = max(0, self.ligne.quantite - retournee)
        # expose property-like for form
        self.ligne.quantite_retournable = self.ligne._qte_retournable
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        form = RetourLigneForm(ligne=self.ligne)
        return render(request, self.template_name, {"form": form, "vente": self.vente, "ligne": self.ligne})

    def post(self, request, *args, **kwargs):
        form = RetourLigneForm(request.POST, ligne=self.ligne)
        if form.is_valid():
            try:
                enregistrer_retour_ligne(
                    ligne_vente=self.ligne,
                    quantite=form.cleaned_data["quantite"],
                    motif=form.cleaned_data["motif"],
                    reintegrable=form.cleaned_data["reintegrable"],
                    utilisateur=request.user,
                    request=request,
                )
            except (ValidationError, PermissionDenied) as e:
                msgs = e.messages if hasattr(e, "messages") else [str(e)]
                for m in msgs:
                    form.add_error(None, m)
            else:
                messages.success(request, "Retour enregistré avec succès.")
                return redirect("ventes:detail", pk=self.vente.pk)
        return render(request, self.template_name, {"form": form, "vente": self.vente, "ligne": self.ligne})


class AnnulationVenteView(ConnexionRequiseMixin, View):
    template_name = "ventes/annulation_formulaire.html"

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or request.user.a_un_role(PHARMACIEN_RESPONSABLE, ADMINISTRATEUR)):
            raise PermissionDenied("Action réservée au pharmacien responsable ou à l'administrateur.")
        self.vente = get_object_or_404(Vente, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if self.vente.statut != Vente.Statut.VALIDEE or self.vente.retours.exists():
            messages.error(request, "Cette vente ne peut pas être annulée.")
            return redirect("ventes:detail", pk=self.vente.pk)
        form = AnnulationVenteForm()
        return render(request, self.template_name, {"form": form, "vente": self.vente})

    def post(self, request, *args, **kwargs):
        if self.vente.statut != Vente.Statut.VALIDEE or self.vente.retours.exists():
            messages.error(request, "Cette vente ne peut pas être annulée.")
            return redirect("ventes:detail", pk=self.vente.pk)
        form = AnnulationVenteForm(request.POST)
        if form.is_valid():
            try:
                annuler_vente(vente=self.vente, motif=form.cleaned_data["motif"], utilisateur=request.user, request=request)
            except (ValidationError, PermissionDenied) as e:
                msgs = e.messages if hasattr(e, "messages") else [str(e)]
                for m in msgs:
                    form.add_error(None, m)
            else:
                messages.success(request, "Vente annulée (opération compensatoire enregistrée).")
                return redirect("ventes:detail", pk=self.vente.pk)
        return render(request, self.template_name, {"form": form, "vente": self.vente})


class RecuVenteView(PermissionRequiseMixin, DetailView):
    model = Vente
    template_name = "ventes/recu.html"
    context_object_name = "vente"
    permission_required = "ventes.view_vente"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("client", "auteur")
            .prefetch_related("lignes__lot__medicament", "paiements")
        )
