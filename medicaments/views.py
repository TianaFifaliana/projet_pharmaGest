from django.contrib import messages
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from utilisateurs.mixins import PermissionRequiseMixin

from .forms import FormulaireCategorie, FormulaireMedicament
from .models import Categorie, Medicament


class ListeMedicamentsView(PermissionRequiseMixin, ListView):
    model = Medicament
    template_name = "medicaments/liste.html"
    context_object_name = "medicaments"
    permission_required = "medicaments.view_medicament"
    paginate_by = 15

    TRIS = {
        "nom": ("nom_commercial", "nom_generique"),
        "-nom": ("-nom_commercial", "-nom_generique"),
        "prix": ("prix_vente", "nom_commercial"),
        "-prix": ("-prix_vente", "nom_commercial"),
        "categorie": ("categorie__nom", "nom_commercial"),
        "-categorie": ("-categorie__nom", "nom_commercial"),
        "recent": ("-date_creation",),
        "ancien": ("date_creation",),
    }

    def get_queryset(self):
        queryset = super().get_queryset().select_related("categorie")

        recherche = self.request.GET.get("q", "").strip()
        if recherche:
            queryset = queryset.filter(
                Q(nom_commercial__icontains=recherche)
                | Q(nom_generique__icontains=recherche)
                | Q(code_barres__icontains=recherche)
            )

        categorie = self.request.GET.get("categorie", "").strip()
        if categorie.isdigit():
            queryset = queryset.filter(categorie_id=categorie)

        statut = self.request.GET.get("statut", "").strip()
        if statut in Medicament.Statut.values:
            queryset = queryset.filter(statut=statut)

        tri = self.request.GET.get("tri", "nom")
        return queryset.order_by(*self.TRIS.get(tri, self.TRIS["nom"]))

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte.update(
            {
                "categories": Categorie.objects.all(),
                "recherche": self.request.GET.get("q", ""),
                "categorie_filtre": self.request.GET.get("categorie", ""),
                "statut_filtre": self.request.GET.get("statut", ""),
                "tri_filtre": self.request.GET.get("tri", "nom"),
                "tris": (
                    ("nom", "Nom (A → Z)"),
                    ("-nom", "Nom (Z → A)"),
                    ("prix", "Prix croissant"),
                    ("-prix", "Prix décroissant"),
                    ("categorie", "Catégorie (A → Z)"),
                    ("-categorie", "Catégorie (Z → A)"),
                    ("recent", "Plus récents"),
                    ("ancien", "Plus anciens"),
                ),
                "total_medicaments": Medicament.objects.count(),
                "total_actifs": Medicament.objects.filter(
                    statut=Medicament.Statut.ACTIF
                ).count(),
                "total_archives": Medicament.objects.filter(
                    statut=Medicament.Statut.ARCHIVE
                ).count(),
            }
        )
        return contexte


class DetailMedicamentView(PermissionRequiseMixin, DetailView):
    model = Medicament
    template_name = "medicaments/detail.html"
    context_object_name = "medicament"
    permission_required = "medicaments.view_medicament"

    def get_queryset(self):
        return super().get_queryset().select_related("categorie")

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        medicament = self.object
        contexte.update(
            {
                "lots": medicament.lots.all()[:20],
                "nombre_lots": medicament.lots.count(),
                "nombre_lignes_achat": medicament.lignes_achat.count(),
                "a_un_historique": medicament.a_un_historique,
            }
        )
        return contexte


class CreationMedicamentView(PermissionRequiseMixin, CreateView):
    model = Medicament
    form_class = FormulaireMedicament
    template_name = "medicaments/formulaire.html"
    permission_required = "medicaments.add_medicament"

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte.update(
            {
                "titre": "Ajouter un médicament",
                "bouton": "Enregistrer le médicament",
                "mode_creation": True,
            }
        )
        return contexte

    def form_valid(self, form):
        reponse = super().form_valid(form)
        messages.success(
            self.request,
            f"Le médicament « {self.object} » a été créé avec succès.",
        )
        return reponse

    def get_success_url(self):
        return reverse("medicaments:detail", args=[self.object.pk])


class ModificationMedicamentView(PermissionRequiseMixin, UpdateView):
    model = Medicament
    form_class = FormulaireMedicament
    template_name = "medicaments/formulaire.html"
    permission_required = "medicaments.change_medicament"

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte.update(
            {
                "titre": f"Modifier {self.object}",
                "bouton": "Enregistrer les modifications",
                "mode_creation": False,
            }
        )
        return contexte

    def form_valid(self, form):
        reponse = super().form_valid(form)
        messages.success(
            self.request,
            f"Le médicament « {self.object} » a été mis à jour.",
        )
        return reponse

    def get_success_url(self):
        return reverse("medicaments:detail", args=[self.object.pk])


class SuppressionMedicamentView(PermissionRequiseMixin, View):
    permission_required = "medicaments.delete_medicament"
    template_name = "medicaments/confirmation_suppression.html"

    def _contexte(self, medicament):
        return {
            "medicament": medicament,
            "a_un_historique": medicament.a_un_historique,
        }

    def get(self, request, pk):
        medicament = get_object_or_404(Medicament, pk=pk)
        return render(request, self.template_name, self._contexte(medicament))

    def post(self, request, pk):
        medicament = get_object_or_404(Medicament, pk=pk)
        libelle = str(medicament)

        if medicament.a_un_historique:
            medicament.statut = Medicament.Statut.ARCHIVE
            medicament.save(update_fields=["statut", "date_modification"])
            messages.warning(
                request,
                f"« {libelle} » possède un historique (stock, achats ou ventes). "
                "Il a été archivé au lieu d'être supprimé afin de préserver la "
                "traçabilité. Il reste consultable mais n'est plus actif.",
            )
        else:
            medicament.delete()
            messages.success(request, f"Le médicament « {libelle} » a été supprimé.")

        return redirect("medicaments:liste")


class ListeCategoriesView(PermissionRequiseMixin, ListView):
    model = Categorie
    template_name = "medicaments/categories/liste.html"
    context_object_name = "categories"
    permission_required = "medicaments.view_categorie"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .annotate(nombre_medicaments=Count("medicaments"))
            .order_by("nom")
        )
        recherche = self.request.GET.get("q", "").strip()
        if recherche:
            queryset = queryset.filter(
                Q(nom__icontains=recherche)
                | Q(description__icontains=recherche)
            )
        return queryset

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte.update(
            {
                "recherche": self.request.GET.get("q", ""),
                "total_categories": Categorie.objects.count(),
            }
        )
        return contexte


class CreationCategorieView(PermissionRequiseMixin, CreateView):
    model = Categorie
    form_class = FormulaireCategorie
    template_name = "medicaments/categories/formulaire.html"
    permission_required = "medicaments.add_categorie"
    success_url = reverse_lazy("medicaments:categories")

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte.update(
            {
                "titre": "Ajouter une catégorie",
                "bouton": "Enregistrer la catégorie",
                "mode_creation": True,
            }
        )
        return contexte

    def form_valid(self, form):
        reponse = super().form_valid(form)
        messages.success(
            self.request,
            f"La catégorie « {self.object.nom} » a été créée avec succès.",
        )
        return reponse


class ModificationCategorieView(PermissionRequiseMixin, UpdateView):
    model = Categorie
    form_class = FormulaireCategorie
    template_name = "medicaments/categories/formulaire.html"
    permission_required = "medicaments.change_categorie"
    success_url = reverse_lazy("medicaments:categories")

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte.update(
            {
                "titre": f"Modifier {self.object.nom}",
                "bouton": "Enregistrer les modifications",
                "mode_creation": False,
            }
        )
        return contexte

    def form_valid(self, form):
        reponse = super().form_valid(form)
        messages.success(
            self.request,
            f"La catégorie « {self.object.nom} » a été mise à jour.",
        )
        return reponse


class SuppressionCategorieView(PermissionRequiseMixin, View):
    permission_required = "medicaments.delete_categorie"
    template_name = "medicaments/categories/confirmation_suppression.html"

    def _contexte(self, categorie):
        return {
            "categorie": categorie,
            "nombre_medicaments": categorie.medicaments.count(),
        }

    def get(self, request, pk):
        categorie = get_object_or_404(Categorie, pk=pk)
        return render(request, self.template_name, self._contexte(categorie))

    def post(self, request, pk):
        categorie = get_object_or_404(Categorie, pk=pk)
        nombre = categorie.medicaments.count()
        if nombre:
            messages.error(
                request,
                f"La catégorie « {categorie.nom} » ne peut pas être supprimée : "
                f"elle est utilisée par {nombre} médicament"
                f"{'s' if nombre > 1 else ''}. Réaffectez-les à une autre "
                "catégorie avant de réessayer.",
            )
            return redirect("medicaments:categories")

        nom = categorie.nom
        try:
            categorie.delete()
        except ProtectedError:
            messages.error(
                request,
                f"La catégorie « {nom} » ne peut pas être supprimée car elle est "
                "utilisée par des médicaments.",
            )
        else:
            messages.success(request, f"La catégorie « {nom} » a été supprimée.")

        return redirect("medicaments:categories")
