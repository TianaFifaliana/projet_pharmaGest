from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from achats.models import CommandeAchat, ReceptionAchat
from stock.models import LotStock
from stock.services import DEFAULT_JOURS_ALERTE_PEREMPTION
from utilisateurs.roles import ADMINISTRATEUR, CAISSIER, PHARMACIEN_RESPONSABLE, RESPONSABLE_GESTION
from ventes.models import LigneVente, Paiement, Vente

from .forms import PeriodeDashboardForm
from . import pdf as pdfgen


def _pdf_response(buf, filename):
    resp = HttpResponse(buf.getvalue(), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


def _scope_ventes_propres(user):
    return bool(
        user.a_un_role(CAISSIER)
        and not (
            user.is_superuser
            or user.a_un_role(RESPONSABLE_GESTION, PHARMACIEN_RESPONSABLE, ADMINISTRATEUR)
        )
    )


def _verifier_acces_vente(user, vente):
    if _scope_ventes_propres(user) and vente.auteur_id != user.id:
        raise PermissionDenied("Vous ne pouvez accéder qu'à vos propres ventes.")


@login_required
@permission_required("ventes.view_vente", raise_exception=True)
def recu_vente_pdf(request, pk):
    vente = get_object_or_404(Vente.objects.prefetch_related("lignes__lot__medicament", "paiements"), pk=pk)
    _verifier_acces_vente(request.user, vente)
    buf = pdfgen.pdf_recu_vente(vente)
    return _pdf_response(buf, f"recu_{vente.numero}.pdf")


@login_required
@permission_required("ventes.view_vente", raise_exception=True)
def facture_vente_pdf(request, pk):
    vente = get_object_or_404(Vente.objects.prefetch_related("lignes__lot__medicament", "paiements"), pk=pk)
    _verifier_acces_vente(request.user, vente)
    buf = pdfgen.pdf_facture_vente(vente)
    return _pdf_response(buf, f"facture_{vente.numero}.pdf")


@login_required
@permission_required("achats.view_commandeachat", raise_exception=True)
def bon_commande_pdf(request, pk):
    commande = get_object_or_404(
        CommandeAchat.objects.select_related("fournisseur", "auteur").prefetch_related("lignes__medicament"),
        pk=pk,
    )
    buf = pdfgen.pdf_bon_commande(commande)
    return _pdf_response(buf, f"bon_commande_{commande.numero}.pdf")


@login_required
@permission_required("achats.view_receptionachat", raise_exception=True)
def bon_reception_pdf(request, pk):
    reception = get_object_or_404(
        ReceptionAchat.objects.select_related("commande", "commande__fournisseur", "auteur", "validee_par")
        .prefetch_related("lignes__ligne_achat__medicament", "lignes__lot"),
        pk=pk,
    )
    buf = pdfgen.pdf_bon_reception(reception)
    return _pdf_response(buf, f"bon_reception_{reception.numero}.pdf")


@login_required
@permission_required("stock.view_lotstock", raise_exception=True)
def rapport_stock_pdf(request):
    lots = LotStock.objects.select_related("medicament").order_by("medicament__nom_commercial", "date_peremption")
    date_doc = timezone.localdate().strftime("%d/%m/%Y")
    buf = pdfgen.pdf_rapport_stock(lots, date_doc)
    return _pdf_response(buf, f"rapport_stock_{timezone.localdate():%Y%m%d}.pdf")


@login_required
@permission_required("ventes.view_vente", raise_exception=True)
def rapport_ventes_pdf(request):
    form = PeriodeDashboardForm(request.GET or None)
    today = timezone.localdate()
    if form.is_valid():
        date_debut = form.cleaned_data.get("date_debut") or today.replace(day=1)
        date_fin = form.cleaned_data.get("date_fin") or today
    else:
        date_debut, date_fin = today.replace(day=1), today

    user = request.user
    ventes = Vente.objects.filter(
        statut=Vente.Statut.VALIDEE,
        date_validation__date__gte=date_debut,
        date_validation__date__lte=date_fin,
    ).select_related("client", "auteur").prefetch_related("lignes__lot__medicament")
    if _scope_ventes_propres(user):
        ventes = ventes.filter(auteur=user)

    ventes_list = list(ventes.order_by("date_validation"))
    lignes = LigneVente.objects.filter(vente__in=ventes)
    ca = lignes.aggregate(total=Coalesce(Sum(F("quantite") * F("prix_applique")), Value(Decimal("0.00")), output_field=DecimalField(max_digits=14, decimal_places=2)))["total"] or Decimal("0.00")
    cout = lignes.aggregate(total=Coalesce(Sum(F("quantite") * F("lot__medicament__prix_achat")), Value(Decimal("0.00")), output_field=DecimalField(max_digits=14, decimal_places=2)))["total"] or Decimal("0.00")
    enc_qs = Paiement.objects.filter(statut=Paiement.Statut.VALIDE, date_paiement__date__gte=date_debut, date_paiement__date__lte=date_fin, vente__in=ventes)
    encaissements = enc_qs.aggregate(total=Coalesce(Sum("montant"), Value(Decimal("0.00")), output_field=DecimalField(max_digits=14, decimal_places=2)))["total"] or Decimal("0.00")
    totaux = {"ca": ca, "encaissements": encaissements, "marge": ca - cout}
    buf = pdfgen.pdf_rapport_ventes(ventes_list, date_debut, date_fin, totaux)
    return _pdf_response(buf, f"rapport_ventes_{date_debut:%Y%m%d}_{date_fin:%Y%m%d}.pdf")


@login_required
@permission_required("achats.view_receptionachat", raise_exception=True)
def rapport_achats_pdf(request):
    form = PeriodeDashboardForm(request.GET or None)
    today = timezone.localdate()
    if form.is_valid():
        date_debut = form.cleaned_data.get("date_debut") or today.replace(day=1)
        date_fin = form.cleaned_data.get("date_fin") or today
    else:
        date_debut, date_fin = today.replace(day=1), today

    receptions = (
        ReceptionAchat.objects.filter(
            est_validee=True,
            date_validation__date__gte=date_debut,
            date_validation__date__lte=date_fin,
        )
        .select_related("commande", "commande__fournisseur")
        .prefetch_related("lignes__ligne_achat")
        .order_by("date_validation")
    )
    rec_list = list(receptions)
    total = sum((r.montant_total for r in rec_list), Decimal("0.00"))
    buf = pdfgen.pdf_rapport_achats(rec_list, date_debut, date_fin, total)
    return _pdf_response(buf, f"rapport_achats_{date_debut:%Y%m%d}_{date_fin:%Y%m%d}.pdf")


@login_required
@permission_required("stock.view_lotstock", raise_exception=True)
def produits_peremption_pdf(request):
    try:
        jours = int(request.GET.get("jours", DEFAULT_JOURS_ALERTE_PEREMPTION))
    except (TypeError, ValueError):
        jours = DEFAULT_JOURS_ALERTE_PEREMPTION
    jours = max(1, min(jours, 365))
    today = timezone.localdate()
    limite = today + timedelta(days=jours)
    lots = (
        LotStock.objects.select_related("medicament")
        .filter(date_peremption__gte=today, date_peremption__lte=limite, quantite_disponible__gt=0, bloque=False)
        .order_by("date_peremption", "medicament__nom_commercial")
    )
    buf = pdfgen.pdf_produits_peremption(lots, jours)
    return _pdf_response(buf, f"produits_peremption_{jours}j_{today:%Y%m%d}.pdf")
