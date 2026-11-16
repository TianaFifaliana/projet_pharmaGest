from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from achats.models import CommandeAchat, LigneAchat, LigneReception
from rapports.models import JournalAudit
from stock.services import journaliser
from utilisateurs.mixins import PermissionRequiseMixin, permission_requise

from .forms import FormulaireFournisseur
from .models import Fournisseur

CHAMP_MONTANT = DecimalField(max_digits=16, decimal_places=2)


def _total(queryset, expression):
    resultat = queryset.aggregate(total=Sum(ExpressionWrapper(expression, output_field=CHAMP_MONTANT)))["total"]
    return resultat or Decimal("0.00")


def _montant_receptionne(commande):
    return sum((ligne.montant_ligne for reception in commande.receptions.all() if reception.est_validee for ligne in reception.lignes.all()), Decimal("0.00"))


def _totaux_achats(fournisseur):
    lignes_commandees = LigneAchat.objects.filter(commande__fournisseur=fournisseur).exclude(commande__statut=CommandeAchat.Statut.ANNULEE)
    lignes_recues = LigneReception.objects.filter(reception__commande__fournisseur=fournisseur, reception__est_validee=True).exclude(reception__commande__statut=CommandeAchat.Statut.ANNULEE)
    return {
        "total_commande": _total(lignes_commandees, F("prix_unitaire") * F("quantite")),
        "total_receptionne": _total(lignes_recues, F("quantite") * F("ligne_achat__prix_unitaire")),
    }


class ListeFournisseursView(PermissionRequiseMixin, ListView):
    model = Fournisseur
    template_name = "fournisseurs/liste.html"
    context_object_name = "fournisseurs"
    permission_required = "fournisseurs.view_fournisseur"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().annotate(nombre_commandes=Count("commandes")).order_by("nom")
        recherche = self.request.GET.get("q", "").strip()
        if recherche:
            queryset = queryset.filter(Q(nom__icontains=recherche) | Q(telephone__icontains=recherche) | Q(contact__icontains=recherche) | Q(email__icontains=recherche) | Q(ville__icontains=recherche))
        statut = self.request.GET.get("statut", "").strip()
        if statut == "actifs":
            queryset = queryset.filter(actif=True)
        elif statut == "inactifs":
            queryset = queryset.filter(actif=False)
        return queryset

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte.update({
            "recherche": self.request.GET.get("q", ""), "statut_filtre": self.request.GET.get("statut", ""),
            "total_fournisseurs": Fournisseur.objects.count(), "total_actifs": Fournisseur.objects.filter(actif=True).count(), "total_inactifs": Fournisseur.objects.filter(actif=False).count(),
        })
        return contexte


class DetailFournisseurView(PermissionRequiseMixin, DetailView):
    model = Fournisseur
    template_name = "fournisseurs/detail.html"
    context_object_name = "fournisseur"
    permission_required = "fournisseurs.view_fournisseur"

    def get_queryset(self):
        return super().get_queryset().annotate(nombre_commandes=Count("commandes"))

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        fournisseur = self.object
        commandes_qs = fournisseur.commandes.select_related().prefetch_related("lignes", "receptions__lignes__ligne_achat").order_by("-date_creation", "-pk")
        nombre_commandes = commandes_qs.count()
        commandes = list(commandes_qs[:20])
        for commande in commandes:
            commande.montant_receptionne = _montant_receptionne(commande)
        contexte.update({"commandes": commandes, "nombre_commandes": nombre_commandes, "commandes_tronquees": nombre_commandes > len(commandes), "nombre_commandes_annulees": fournisseur.commandes.filter(statut=CommandeAchat.Statut.ANNULEE).count(), **_totaux_achats(fournisseur)})
        return contexte


class CreationFournisseurView(PermissionRequiseMixin, CreateView):
    model = Fournisseur
    form_class = FormulaireFournisseur
    template_name = "fournisseurs/formulaire.html"
    permission_required = "fournisseurs.add_fournisseur"

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte.update({"titre": "Ajouter un fournisseur", "bouton": "Enregistrer le fournisseur", "mode_creation": True})
        return contexte

    def form_valid(self, form):
        reponse = super().form_valid(form)
        journaliser(self.request, self.request.user, JournalAudit.Action.CREATION, self.object, f"Fournisseur créé : {self.object.nom}")
        messages.success(self.request, f"Le fournisseur « {self.object.nom} » a été créé avec succès.")
        return reponse

    def get_success_url(self):
        return reverse("fournisseurs:detail", args=[self.object.pk])


class ModificationFournisseurView(PermissionRequiseMixin, UpdateView):
    model = Fournisseur
    form_class = FormulaireFournisseur
    template_name = "fournisseurs/formulaire.html"
    permission_required = "fournisseurs.change_fournisseur"

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte.update({"titre": f"Modifier {self.object.nom}", "bouton": "Enregistrer les modifications", "mode_creation": False})
        return contexte

    def form_valid(self, form):
        reponse = super().form_valid(form)
        journaliser(self.request, self.request.user, JournalAudit.Action.MODIFICATION, self.object, f"Fournisseur modifié : {self.object.nom}")
        messages.success(self.request, f"Le fournisseur « {self.object.nom} » a été mis à jour.")
        return reponse

    def get_success_url(self):
        return reverse("fournisseurs:detail", args=[self.object.pk])


class SuppressionFournisseurView(PermissionRequiseMixin, View):
    permission_required = "fournisseurs.delete_fournisseur"
    template_name = "fournisseurs/confirmation_suppression.html"

    def _contexte(self, fournisseur):
        return {"fournisseur": fournisseur, "nombre_commandes": fournisseur.commandes.count()}

    def get(self, request, pk):
        return render(request, self.template_name, self._contexte(get_object_or_404(Fournisseur, pk=pk)))

    def post(self, request, pk):
        fournisseur = get_object_or_404(Fournisseur, pk=pk)
        nombre = fournisseur.commandes.count()
        if nombre:
            messages.error(request, f"Le fournisseur « {fournisseur.nom} » ne peut pas être supprimé : il possède {nombre} commande(s). Désactivez-le pour préserver l'historique.")
            return redirect("fournisseurs:detail", pk=fournisseur.pk)
        nom = fournisseur.nom
        pk_obj = fournisseur.pk
        fournisseur.delete()
        JournalAudit.objects.create(utilisateur=request.user, action=JournalAudit.Action.SUPPRESSION, modele="Fournisseur", objet_id=str(pk_obj), description=f"Fournisseur supprimé : {nom}")
        messages.success(request, f"Le fournisseur « {nom} » a été supprimé.")
        return redirect("fournisseurs:liste")


def _changer_statut(request, fournisseur, actif):
    if request.method == "POST":
        if fournisseur.actif != actif:
            fournisseur.actif = actif
            fournisseur.save(update_fields=["actif"])
            action_txt = "activé" if actif else "désactivé"
            journaliser(request, request.user, JournalAudit.Action.MODIFICATION, fournisseur, f"Fournisseur {action_txt} : {fournisseur.nom}")
            messages.success(request, f"Le fournisseur « {fournisseur.nom} » a été {action_txt}.")
        else:
            messages.info(request, "Le statut du fournisseur était déjà à jour.")
        return redirect("fournisseurs:detail", pk=fournisseur.pk)
    return render(request, "fournisseurs/confirmation_statut.html", {"fournisseur": fournisseur, "activation": actif})


@permission_requise("fournisseurs.change_fournisseur")
def activer_fournisseur(request, pk):
    return _changer_statut(request, get_object_or_404(Fournisseur, pk=pk), True)


@permission_requise("fournisseurs.change_fournisseur")
def desactiver_fournisseur(request, pk):
    return _changer_statut(request, get_object_or_404(Fournisseur, pk=pk), False)
