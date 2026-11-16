from datetime import datetime

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views import View
from django.views.generic import DetailView, ListView

from fournisseurs.models import Fournisseur
from rapports.models import JournalAudit
from utilisateurs.mixins import PermissionRequiseMixin

from .forms import (
    FormulaireCommandeAchat,
    FormulaireLigneReception,
    FormulaireReceptionAchat,
    LigneAchatFormSet,
)
from .models import CommandeAchat, ReceptionAchat
from .services import changer_statut, journaliser, valider_reception


def _parse_date(valeur):
    if not valeur:
        return None
    try:
        return parse_date(valeur)
    except Exception:
        return None


class ListeCommandesAchatView(PermissionRequiseMixin, ListView):
    model = CommandeAchat
    template_name = "achats/liste.html"
    context_object_name = "commandes"
    permission_required = "achats.view_commandeachat"
    paginate_by = 20

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("fournisseur", "auteur")
            .prefetch_related("lignes", "receptions__lignes__ligne_achat")
        )
        fournisseur = self.request.GET.get("fournisseur", "").strip()
        if fournisseur.isdigit():
            qs = qs.filter(fournisseur_id=fournisseur)
        statut = self.request.GET.get("statut", "").strip()
        if statut in CommandeAchat.Statut.values:
            qs = qs.filter(statut=statut)
        date_debut = _parse_date(self.request.GET.get("date_debut", "").strip())
        date_fin = _parse_date(self.request.GET.get("date_fin", "").strip())
        if date_debut:
            qs = qs.filter(date_creation__date__gte=date_debut)
        if date_fin:
            qs = qs.filter(date_creation__date__lte=date_fin)
        recherche = self.request.GET.get("q", "").strip()
        if recherche:
            qs = qs.filter(numero__icontains=recherche)
        return qs

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte.update(
            {
                "fournisseurs": Fournisseur.objects.order_by("nom"),
                "statuts": CommandeAchat.Statut.choices,
                "fournisseur_filtre": self.request.GET.get("fournisseur", ""),
                "statut_filtre": self.request.GET.get("statut", ""),
                "date_debut_filtre": self.request.GET.get("date_debut", ""),
                "date_fin_filtre": self.request.GET.get("date_fin", ""),
                "recherche": self.request.GET.get("q", ""),
                "total_commandes": CommandeAchat.objects.count(),
            }
        )
        return contexte


class DetailCommandeAchatView(PermissionRequiseMixin, DetailView):
    model = CommandeAchat
    template_name = "achats/detail.html"
    context_object_name = "commande"
    permission_required = "achats.view_commandeachat"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("fournisseur", "auteur")
            .prefetch_related(
                "lignes__medicament",
                "lignes__lignes_reception__reception",
                "receptions__lignes__ligne_achat__medicament",
                "receptions__lignes__lot",
                "receptions__auteur",
                "receptions__validee_par",
            )
        )

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        commande = self.object
        receptions = list(commande.receptions.all())
        contexte.update(
            {
                "receptions": receptions,
                "peut_modifier": commande.statut == CommandeAchat.Statut.BROUILLON,
                "peut_commander": commande.statut == CommandeAchat.Statut.BROUILLON,
                "peut_annuler": commande.statut in {
                    CommandeAchat.Statut.BROUILLON,
                    CommandeAchat.Statut.COMMANDEE,
                    CommandeAchat.Statut.PARTIELLEMENT_RECEPTIONNEE,
                },
                "peut_receptionner": commande.statut in {
                    CommandeAchat.Statut.COMMANDEE,
                    CommandeAchat.Statut.PARTIELLEMENT_RECEPTIONNEE,
                },
            }
        )
        return contexte


class CreationCommandeAchatView(PermissionRequiseMixin, View):
    permission_required = "achats.add_commandeachat"
    template_name = "achats/formulaire.html"

    def get(self, request):
        commande = CommandeAchat()
        form = FormulaireCommandeAchat(instance=commande)
        formset = LigneAchatFormSet(instance=commande, prefix="lignes")
        return render(request, self.template_name, self._contexte(form, formset, True))

    def post(self, request):
        commande = CommandeAchat(auteur=request.user)
        form = FormulaireCommandeAchat(request.POST, instance=commande)
        formset = LigneAchatFormSet(request.POST, instance=commande, prefix="lignes")
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    commande = form.save(commit=False)
                    commande.auteur = request.user
                    commande.statut = CommandeAchat.Statut.BROUILLON
                    commande.save()
                    formset.instance = commande
                    formset.save()
                    journaliser(
                        request,
                        request.user,
                        JournalAudit.Action.CREATION,
                        commande,
                        f"Commande créée ({commande.fournisseur}).",
                    )
            except ValidationError as e:
                form.add_error(None, e)
            else:
                messages.success(request, f"La commande {commande.numero} a été créée.")
                return redirect("achats:detail", pk=commande.pk)
        return render(request, self.template_name, self._contexte(form, formset, True))

    def _contexte(self, form, formset, mode_creation):
        return {
            "form": form,
            "formset": formset,
            "titre": "Nouvelle commande d'achat",
            "bouton": "Enregistrer le brouillon",
            "mode_creation": mode_creation,
        }


class ModificationCommandeAchatView(PermissionRequiseMixin, View):
    permission_required = "achats.change_commandeachat"
    template_name = "achats/formulaire.html"

    def _get_commande(self, pk):
        return get_object_or_404(CommandeAchat, pk=pk)

    def get(self, request, pk):
        commande = self._get_commande(pk)
        if commande.statut != CommandeAchat.Statut.BROUILLON:
            messages.error(request, "Seule une commande en brouillon peut être modifiée.")
            return redirect("achats:detail", pk=commande.pk)
        form = FormulaireCommandeAchat(instance=commande)
        formset = LigneAchatFormSet(instance=commande, prefix="lignes")
        return render(request, self.template_name, self._contexte(commande, form, formset))

    def post(self, request, pk):
        commande = self._get_commande(pk)
        if commande.statut != CommandeAchat.Statut.BROUILLON:
            messages.error(request, "Seule une commande en brouillon peut être modifiée.")
            return redirect("achats:detail", pk=commande.pk)
        form = FormulaireCommandeAchat(request.POST, instance=commande)
        formset = LigneAchatFormSet(request.POST, instance=commande, prefix="lignes")
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    form.save()
                    formset.save()
                    journaliser(
                        request,
                        request.user,
                        JournalAudit.Action.MODIFICATION,
                        commande,
                        "Commande modifiée.",
                    )
            except ValidationError as e:
                form.add_error(None, e)
            else:
                messages.success(request, f"La commande {commande.numero} a été mise à jour.")
                return redirect("achats:detail", pk=commande.pk)
        return render(request, self.template_name, self._contexte(commande, form, formset))

    def _contexte(self, commande, form, formset):
        return {
            "commande": commande,
            "form": form,
            "formset": formset,
            "titre": f"Modifier {commande.numero}",
            "bouton": "Enregistrer les modifications",
            "mode_creation": False,
        }


class CommandeStatutActionView(PermissionRequiseMixin, View):
    permission_required = "achats.change_commandeachat"

    def post(self, request, pk, action):
        commande = get_object_or_404(CommandeAchat, pk=pk)
        mapping = {
            "commander": CommandeAchat.Statut.COMMANDEE,
            "annuler": CommandeAchat.Statut.ANNULEE,
        }
        nouveau = mapping.get(action)
        if not nouveau:
            messages.error(request, "Action inconnue.")
            return redirect("achats:detail", pk=commande.pk)
        try:
            changer_statut(commande, nouveau, request=request)
        except ValidationError as e:
            messages.error(request, "; ".join(e.messages) if hasattr(e, "messages") else str(e))
        else:
            if nouveau == CommandeAchat.Statut.COMMANDEE:
                messages.success(request, f"La commande {commande.numero} a été validée.")
            else:
                messages.warning(request, f"La commande {commande.numero} a été annulée.")
        return redirect("achats:detail", pk=commande.pk)


class ReceptionCommandeView(PermissionRequiseMixin, View):
    permission_required = "achats.add_receptionachat"
    template_name = "achats/reception_formulaire.html"

    def _get_commande(self, pk):
        return get_object_or_404(
            CommandeAchat.objects.select_related("fournisseur").prefetch_related(
                "lignes__medicament", "lignes__lignes_reception"
            ),
            pk=pk,
        )

    def _build_rows(self, commande, post_data=None):
        rows = []
        for ligne in commande.lignes.all():
            prefix = f"ligne_{ligne.pk}"
            form = FormulaireLigneReception(
                post_data,
                prefix=prefix,
                ligne_achat=ligne,
            )
            rows.append({"ligne": ligne, "form": form})
        return rows

    def get(self, request, pk):
        commande = self._get_commande(pk)
        if commande.statut not in {
            CommandeAchat.Statut.COMMANDEE,
            CommandeAchat.Statut.PARTIELLEMENT_RECEPTIONNEE,
        }:
            messages.error(request, "Cette commande ne peut pas être réceptionnée dans son état actuel.")
            return redirect("achats:detail", pk=commande.pk)
        form_reception = FormulaireReceptionAchat()
        rows = self._build_rows(commande)
        return render(request, self.template_name, self._contexte(commande, form_reception, rows))

    def post(self, request, pk):
        commande = self._get_commande(pk)
        if commande.statut not in {
            CommandeAchat.Statut.COMMANDEE,
            CommandeAchat.Statut.PARTIELLEMENT_RECEPTIONNEE,
        }:
            messages.error(request, "Cette commande ne peut pas être réceptionnée dans son état actuel.")
            return redirect("achats:detail", pk=commande.pk)
        form_reception = FormulaireReceptionAchat(request.POST)
        rows = self._build_rows(commande, request.POST)
        forms_valides = form_reception.is_valid() and all(r["form"].is_valid() for r in rows)
        if forms_valides:
            lignes_data = []
            for r in rows:
                cd = r["form"].cleaned_data
                qte = cd.get("quantite") or 0
                if qte > 0:
                    lignes_data.append(
                        {
                            "ligne_achat": r["ligne"],
                            "quantite": qte,
                            "numero_lot": cd.get("numero_lot"),
                            "date_peremption": cd.get("date_peremption"),
                        }
                    )
            reception = ReceptionAchat(commande=commande, auteur=request.user)
            reception.save()  # génère numéro pour référence
            try:
                valider_reception(reception, lignes_data, request=request)
            except ValidationError as e:
                # annuler la réception vide créée si validation échoue
                reception.delete()
                erreurs = e.messages if hasattr(e, "messages") else [str(e)]
                for msg in erreurs:
                    form_reception.add_error(None, msg)
            else:
                messages.success(
                    request,
                    f"La réception {reception.numero} a été validée et le stock a été mis à jour.",
                )
                return redirect("achats:detail", pk=commande.pk)
        return render(request, self.template_name, self._contexte(commande, form_reception, rows))

    def _contexte(self, commande, form_reception, rows):
        return {
            "commande": commande,
            "form_reception": form_reception,
            "rows": rows,
            "titre": f"Réception - {commande.numero}",
        }


class DetailReceptionView(PermissionRequiseMixin, DetailView):
    model = ReceptionAchat
    template_name = "achats/reception_detail.html"
    context_object_name = "reception"
    permission_required = "achats.view_receptionachat"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("commande", "commande__fournisseur", "auteur", "validee_par")
            .prefetch_related("lignes__ligne_achat__medicament", "lignes__lot")
        )
