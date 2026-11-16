from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from utilisateurs.mixins import PermissionRequiseMixin, permission_requise
from ventes.models import LigneVente, Vente

from .forms import FormulaireClient
from .models import Client

CHAMP_MONTANT = DecimalField(max_digits=16, decimal_places=2)


def _total(queryset, expression):
    resultat = queryset.aggregate(
        total=Sum(
            ExpressionWrapper(expression, output_field=CHAMP_MONTANT)
        )
    )["total"]
    return resultat or Decimal("0.00")


class ListeClientsView(PermissionRequiseMixin, ListView):
    model = Client
    template_name = "clients/liste.html"
    context_object_name = "clients"
    permission_required = "clients.view_client"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .annotate(nombre_ventes=Count("ventes"))
            .order_by("nom", "prenom")
        )

        recherche = self.request.GET.get("q", "").strip()
        if recherche:
            queryset = queryset.filter(
                Q(nom__icontains=recherche)
                | Q(prenom__icontains=recherche)
                | Q(telephone__icontains=recherche)
                | Q(email__icontains=recherche)
            )

        statut = self.request.GET.get("statut", "").strip()
        if statut == "actifs":
            queryset = queryset.filter(actif=True)
        elif statut == "inactifs":
            queryset = queryset.filter(actif=False)

        return queryset

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte.update(
            {
                "recherche": self.request.GET.get("q", ""),
                "statut_filtre": self.request.GET.get("statut", ""),
                "total_clients": Client.objects.count(),
                "total_actifs": Client.objects.filter(actif=True).count(),
                "total_inactifs": Client.objects.filter(actif=False).count(),
            }
        )
        return contexte


class DetailClientView(PermissionRequiseMixin, DetailView):
    model = Client
    template_name = "clients/detail.html"
    context_object_name = "client"
    permission_required = "clients.view_client"

    def get_queryset(self):
        return super().get_queryset().annotate(nombre_ventes=Count("ventes"))

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        client = self.object

        ventes_qs = client.ventes.prefetch_related("lignes").order_by(
            "-date_creation", "-pk"
        )
        nombre_ventes = ventes_qs.count()
        ventes = list(ventes_qs[:20])

        montant_ventes = _total(
            LigneVente.objects.filter(vente__client=client).exclude(
                vente__statut=Vente.Statut.ANNULEE
            ),
            F("prix_applique") * F("quantite"),
        )

        contexte.update(
            {
                "ventes": ventes,
                "nombre_ventes": nombre_ventes,
                "ventes_tronquees": nombre_ventes > len(ventes),
                "nombre_ventes_validees": client.ventes.filter(
                    statut=Vente.Statut.VALIDEE
                ).count(),
                "montant_ventes": montant_ventes,
            }
        )
        return contexte


class CreationClientView(PermissionRequiseMixin, CreateView):
    model = Client
    form_class = FormulaireClient
    template_name = "clients/formulaire.html"
    permission_required = "clients.add_client"

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte.update(
            {
                "titre": "Ajouter un client",
                "bouton": "Enregistrer le client",
                "mode_creation": True,
            }
        )
        return contexte

    def form_valid(self, form):
        reponse = super().form_valid(form)
        messages.success(
            self.request,
            f"Le client « {self.object.nom_complet} » a été créé avec succès.",
        )
        return reponse

    def get_success_url(self):
        return reverse("clients:detail", args=[self.object.pk])


class ModificationClientView(PermissionRequiseMixin, UpdateView):
    model = Client
    form_class = FormulaireClient
    template_name = "clients/formulaire.html"
    permission_required = "clients.change_client"

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte.update(
            {
                "titre": f"Modifier {self.object.nom_complet}",
                "bouton": "Enregistrer les modifications",
                "mode_creation": False,
            }
        )
        return contexte

    def form_valid(self, form):
        reponse = super().form_valid(form)
        messages.success(
            self.request,
            f"Le client « {self.object.nom_complet} » a été mis à jour.",
        )
        return reponse

    def get_success_url(self):
        return reverse("clients:detail", args=[self.object.pk])


class SuppressionClientView(PermissionRequiseMixin, View):
    permission_required = "clients.delete_client"
    template_name = "clients/confirmation_suppression.html"

    def _contexte(self, client):
        return {
            "client": client,
            "nombre_ventes": client.ventes.count(),
        }

    def get(self, request, pk):
        client = get_object_or_404(Client, pk=pk)
        return render(request, self.template_name, self._contexte(client))

    def post(self, request, pk):
        client = get_object_or_404(Client, pk=pk)
        nom = client.nom_complet
        nombre = client.ventes.count()
        client.delete()
        messages.success(
            request,
            f"Le client « {nom} » a été supprimé. "
            + (
                f"Ses {nombre} vente{'s' if nombre > 1 else ''} sont conservées "
                "et rattachées aux ventes comptoir."
                if nombre
                else ""
            ),
        )
        return redirect("clients:liste")


def _changer_statut(request, client, actif):
    if request.method == "POST":
        if client.actif != actif:
            client.actif = actif
            client.save(update_fields=["actif"])
            action = "activé" if actif else "désactivé"
            messages.success(
                request,
                f"Le client « {client.nom_complet} » a été {action}. "
                + (
                    "Son historique de ventes est conservé."
                    if not actif
                    else ""
                ),
            )
        else:
            messages.info(request, "Le statut du client était déjà à jour.")
        return redirect("clients:detail", pk=client.pk)

    return render(
        request,
        "clients/confirmation_statut.html",
        {"client": client, "activation": actif},
    )


@permission_requise("clients.change_client")
def activer_client(request, pk):
    client = get_object_or_404(Client, pk=pk)
    return _changer_statut(request, client, True)


@permission_requise("clients.change_client")
def desactiver_client(request, pk):
    client = get_object_or_404(Client, pk=pk)
    return _changer_statut(request, client, False)
