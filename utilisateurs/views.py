from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import FormView, ListView, TemplateView, UpdateView

from rapports.models import JournalAudit
from stock.services import journaliser

from .forms import (
    FormulaireChangementMotDePasse,
    FormulaireConfirmationReinitialisation,
    FormulaireConnexion,
    FormulaireCreationUtilisateur,
    FormulaireModificationUtilisateur,
    FormulaireReinitialisationMotDePasse,
)
from .mixins import ConnexionRequiseMixin, PermissionRequiseMixin, permission_requise
from .models import User
from .roles import ADMINISTRATEUR, ROLES


class AccueilView(ConnexionRequiseMixin, TemplateView):
    template_name = "utilisateurs/accueil.html"


def erreur_403(request, exception=None):
    return render(request, "403.html", status=403)


class ConnexionView(auth_views.LoginView):
    template_name = "utilisateurs/connexion.html"
    authentication_form = FormulaireConnexion
    redirect_authenticated_user = True


class DeconnexionView(auth_views.LogoutView):
    next_page = reverse_lazy("utilisateurs:connexion")


class ChangementMotDePasseView(ConnexionRequiseMixin, auth_views.PasswordChangeView):
    template_name = "utilisateurs/mot_de_passe_changement.html"
    form_class = FormulaireChangementMotDePasse
    success_url = reverse_lazy("utilisateurs:changement_mot_de_passe_termine")


class ChangementMotDePasseTermineView(ConnexionRequiseMixin, auth_views.PasswordChangeDoneView):
    template_name = "utilisateurs/mot_de_passe_changement_termine.html"


class ReinitialisationMotDePasseView(auth_views.PasswordResetView):
    template_name = "utilisateurs/mot_de_passe_reinitialisation.html"
    form_class = FormulaireReinitialisationMotDePasse
    subject_template_name = "utilisateurs/emails/reinitialisation_sujet.txt"
    email_template_name = "utilisateurs/emails/reinitialisation_corps.txt"
    html_email_template_name = "utilisateurs/emails/reinitialisation_corps.html"
    success_url = reverse_lazy("utilisateurs:reinitialisation_mot_de_passe_envoyee")


class ReinitialisationMotDePasseEnvoyeeView(auth_views.PasswordResetDoneView):
    template_name = "utilisateurs/mot_de_passe_reinitialisation_envoyee.html"


class ConfirmationReinitialisationView(auth_views.PasswordResetConfirmView):
    template_name = "utilisateurs/mot_de_passe_reinitialisation_confirmation.html"
    form_class = FormulaireConfirmationReinitialisation
    success_url = reverse_lazy("utilisateurs:reinitialisation_mot_de_passe_terminee")


class ReinitialisationMotDePasseTermineeView(auth_views.PasswordResetCompleteView):
    template_name = "utilisateurs/mot_de_passe_reinitialisation_terminee.html"


class ListeUtilisateursView(PermissionRequiseMixin, ListView):
    model = User
    template_name = "utilisateurs/liste.html"
    context_object_name = "utilisateurs"
    permission_required = "utilisateurs.view_user"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related("groups").order_by("username")
        recherche = self.request.GET.get("q", "").strip()
        if recherche:
            queryset = queryset.filter(
                Q(username__icontains=recherche) | Q(first_name__icontains=recherche) | Q(last_name__icontains=recherche)
                | Q(email__icontains=recherche) | Q(telephone__icontains=recherche)
            )
        role = self.request.GET.get("role", "").strip()
        if role in ROLES:
            queryset = queryset.filter(groups__name=role)
        statut = self.request.GET.get("statut", "").strip()
        if statut == "actifs":
            queryset = queryset.filter(is_active=True)
        elif statut == "inactifs":
            queryset = queryset.filter(is_active=False)
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte.update({
            "roles": ROLES,
            "recherche": self.request.GET.get("q", ""),
            "role_filtre": self.request.GET.get("role", ""),
            "statut_filtre": self.request.GET.get("statut", ""),
            "total_comptes": User.objects.count(),
            "total_actifs": User.objects.filter(is_active=True).count(),
        })
        return contexte


class CreationUtilisateurView(PermissionRequiseMixin, FormView):
    form_class = FormulaireCreationUtilisateur
    template_name = "utilisateurs/formulaire.html"
    permission_required = "utilisateurs.add_user"
    success_url = reverse_lazy("utilisateurs:liste")

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte.update({"titre": "Créer un compte", "bouton": "Créer le compte", "mode_creation": True})
        return contexte

    def form_valid(self, form):
        utilisateur = form.save()
        journaliser(self.request, self.request.user, JournalAudit.Action.CREATION, utilisateur, f"Utilisateur créé : {utilisateur.username}")
        messages.success(self.request, f"Le compte « {utilisateur.username} » a été créé avec succès.")
        return super().form_valid(form)


class ModificationUtilisateurView(PermissionRequiseMixin, UpdateView):
    model = User
    form_class = FormulaireModificationUtilisateur
    template_name = "utilisateurs/formulaire.html"
    permission_required = "utilisateurs.change_user"
    success_url = reverse_lazy("utilisateurs:liste")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["utilisateur_courant"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte.update({"titre": f"Modifier le compte de {self.object.username}", "bouton": "Enregistrer les modifications", "mode_creation": False})
        return contexte

    def form_valid(self, form):
        reponse = super().form_valid(form)
        journaliser(self.request, self.request.user, JournalAudit.Action.MODIFICATION, form.instance, f"Utilisateur modifié : {form.instance.username}")
        messages.success(self.request, f"Le compte « {form.instance.username} » a été mis à jour.")
        return reponse


def _changer_statut(request, utilisateur, actif):
    if utilisateur.pk == request.user.pk and not actif:
        messages.error(request, "Vous ne pouvez pas désactiver votre propre compte.")
        return redirect("utilisateurs:liste")
    if not actif and utilisateur.is_active and utilisateur.a_un_role(ADMINISTRATEUR):
        autres_administrateurs = User.objects.filter(is_active=True, groups__name=ADMINISTRATEUR).exclude(pk=utilisateur.pk).exists()
        if not autres_administrateurs:
            messages.error(request, "Impossible de désactiver le dernier administrateur actif du site.")
            return redirect("utilisateurs:liste")
    if request.method == "POST":
        if utilisateur.is_active != actif:
            utilisateur.is_active = actif
            utilisateur.save(update_fields=["is_active"])
            action_txt = "activé" if actif else "désactivé"
            journaliser(request, request.user, JournalAudit.Action.MODIFICATION, utilisateur, f"Utilisateur {action_txt} : {utilisateur.username}")
            messages.success(request, f"Le compte « {utilisateur.username} » a été {action_txt}.")
        else:
            messages.info(request, "Le statut du compte était déjà à jour.")
        return redirect("utilisateurs:liste")
    return render(request, "utilisateurs/confirmation_statut.html", {"utilisateur_a_modifier": utilisateur, "activation": actif})


@permission_requise("utilisateurs.change_user")
def activer_utilisateur(request, pk):
    return _changer_statut(request, get_object_or_404(User, pk=pk), True)


@permission_requise("utilisateurs.change_user")
def desactiver_utilisateur(request, pk):
    return _changer_statut(request, get_object_or_404(User, pk=pk), False)
