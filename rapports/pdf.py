import io
from datetime import datetime
from decimal import Decimal

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import Parametres


def format_mga(valeur):
    try:
        montant = Decimal(valeur or 0)
    except Exception:
        montant = Decimal("0")
    # Ariary, format simple avec séparateurs d'espace
    s = f"{montant:,.2f}".replace(",", " ").replace(".", ",")
    return f"{s} MGA"


def get_parametres():
    return Parametres.get_solo()


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=8, leading=10, textColor=colors.grey))
    styles.add(ParagraphStyle(name="TitleRight", parent=styles["Heading1"], alignment=2, fontSize=14, leading=16))
    styles.add(ParagraphStyle(name="Muted", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#555555")))
    return styles


def _header(elements, styles, params, titre, numero, date_doc, extra_lines=None):
    left = [f"<b>{params.nom_pharmacie or 'PharmaGest'}</b>"]
    if params.adresse:
        left.append(params.adresse.replace("\n", "<br/>"))
    contact = " | ".join([p for p in [params.telephone, params.email] if p])
    if contact:
        left.append(contact)
    ids = []
    if params.nif:
        ids.append(f"NIF: {params.nif}")
    if params.stat:
        ids.append(f"STAT: {params.stat}")
    if ids:
        left.append(" - ".join(ids))
    right = [f"<b>{titre}</b>", f"N° : {numero}", f"Date : {date_doc}"]
    for line in (extra_lines or []):
        right.append(line)
    header_table = Table(
        [[Paragraph("<br/>".join(left), styles["Normal"]), Paragraph("<br/>".join(right), styles["Normal"])]],
        colWidths=[100 * mm, 80 * mm],
    )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 6 * mm))


def _table(elements, headers, rows, col_widths=None):
    data = [headers] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9ecef")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)


def _footer(elements, styles, params):
    elements.append(Spacer(1, 8 * mm))
    if params.mentions_legales:
        elements.append(Paragraph(params.mentions_legales.replace("\n", "<br/>"), styles["Small"]))
    elements.append(Paragraph(f"Document généré le {timezone.localtime().strftime('%d/%m/%Y %H:%M')}", styles["Small"]))


def build_pdf(titre, numero, date_doc, headers, rows, extra_lines=None, totals=None, col_widths=None):
    params = get_parametres()
    styles = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    elements = []
    _header(elements, styles, params, titre, numero, date_doc, extra_lines=extra_lines)
    _table(elements, headers, rows, col_widths=col_widths)
    if totals:
        elements.append(Spacer(1, 4 * mm))
        trows = [[k, v] for k, v in totals]
        tt = Table(trows, colWidths=[120 * mm, 60 * mm])
        tt.setStyle(TableStyle([
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("LINEABOVE", (0, -1), (-1, -1), 0.5, colors.black),
            ("PADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(tt)
    _footer(elements, styles, params)
    doc.build(elements)
    buf.seek(0)
    return buf


def pdf_recu_vente(vente):
    date_doc = (vente.date_validation or vente.date_creation).strftime("%d/%m/%Y %H:%M")
    extra = [f"Client : {vente.client or 'Comptoir'}", f"Statut : {vente.get_statut_display()}"]
    rows = []
    for l in vente.lignes.all():
        rows.append([str(l.lot.medicament), l.lot.numero_lot, str(l.quantite), format_mga(l.prix_applique), format_mga(l.total_ligne)])
    totals = [("Total", format_mga(vente.montant_total))]
    return build_pdf("Reçu de vente", vente.numero, date_doc, ["Article", "Lot", "Qté", "PU (MGA)", "Total (MGA)"], rows, extra_lines=extra, totals=totals, col_widths=[60*mm,25*mm,15*mm,35*mm,35*mm])


def pdf_facture_vente(vente):
    date_doc = (vente.date_validation or vente.date_creation).strftime("%d/%m/%Y %H:%M")
    extra = [f"Client : {vente.client or 'Comptoir'}", f"Caissier : {vente.auteur}", f"Statut : {vente.get_statut_display()}"]
    rows = []
    for l in vente.lignes.all():
        rows.append([str(l.lot.medicament), l.lot.numero_lot, str(l.quantite), format_mga(l.prix_applique), format_mga(l.total_ligne)])
    tot = vente.montant_total
    paye = getattr(vente, "montant_paye", None)
    totals = [("Total", format_mga(tot))]
    if paye is not None:
        totals.append(("Montant payé (validé)", format_mga(paye)))
    return build_pdf("Facture", vente.numero, date_doc, ["Désignation", "Lot", "Qté", "PU (MGA)", "Total (MGA)"], rows, extra_lines=extra, totals=totals, col_widths=[60*mm,25*mm,15*mm,35*mm,35*mm])


def pdf_bon_commande(commande):
    date_doc = commande.date_creation.strftime("%d/%m/%Y %H:%M")
    extra = [f"Fournisseur : {commande.fournisseur.nom}", f"Statut : {commande.get_statut_display()}", f"Auteur : {commande.auteur}"]
    rows = []
    for l in commande.lignes.all():
        rows.append([str(l.medicament), str(l.quantite), format_mga(l.prix_unitaire), format_mga(l.total_ligne)])
    totals = [("Montant total", format_mga(commande.montant_total))]
    return build_pdf("Bon de commande", commande.numero, date_doc, ["Médicament", "Qté", "PU (MGA)", "Total (MGA)"], rows, extra_lines=extra, totals=totals, col_widths=[80*mm,20*mm,35*mm,35*mm])


def pdf_bon_reception(reception):
    date_doc = (reception.date_validation or reception.date_creation).strftime("%d/%m/%Y %H:%M")
    extra = [f"Commande : {reception.commande.numero}", f"Fournisseur : {reception.commande.fournisseur.nom}", f"Validée : {'Oui' if reception.est_validee else 'Non'}"]
    rows = []
    for l in reception.lignes.all():
        pu = l.prix_unitaire
        rows.append([str(l.ligne_achat.medicament), l.numero_lot, l.date_peremption.strftime("%d/%m/%Y"), str(l.quantite), format_mga(pu), format_mga(l.montant_ligne)])
    totals = [("Montant total réception", format_mga(reception.montant_total))]
    return build_pdf("Bon de réception", reception.numero, date_doc, ["Médicament", "Lot", "Péremption", "Qté", "PU (MGA)", "Total (MGA)"], rows, extra_lines=extra, totals=totals, col_widths=[45*mm,25*mm,25*mm,15*mm,30*mm,30*mm])


def pdf_rapport_stock(lots, date_doc):
    rows = []
    for lot in lots:
        rows.append([str(lot.medicament), lot.numero_lot, lot.date_peremption.strftime("%d/%m/%Y"), str(lot.quantite_disponible), "Oui" if lot.bloque else "Non"])
    numero = f"STK-{timezone.localdate():%Y%m%d}"
    return build_pdf("Rapport de stock", numero, date_doc, ["Médicament", "Lot", "Péremption", "Qté dispo", "Bloqué"], rows, col_widths=[70*mm,30*mm,30*mm,25*mm,20*mm])


def pdf_rapport_ventes(ventes, date_debut, date_fin, totaux):
    rows = []
    for v in ventes:
        rows.append([v.numero, (v.date_validation or v.date_creation).strftime("%d/%m/%Y"), str(v.client or "Comptoir"), v.get_statut_display(), format_mga(v.montant_total)])
    numero = f"RV-{timezone.localdate():%Y%m%d}"
    date_doc = f"{date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}"
    totals = [("Chiffre d'affaires", format_mga(totaux.get("ca", 0))), ("Encaissements", format_mga(totaux.get("encaissements", 0))), ("Marge commerciale", format_mga(totaux.get("marge", 0)))]
    return build_pdf("Rapport des ventes", numero, date_doc, ["N°", "Date", "Client", "Statut", "Montant (MGA)"], rows, totals=totals, col_widths=[35*mm,25*mm,45*mm,30*mm,35*mm])


def pdf_rapport_achats(receptions, date_debut, date_fin, total):
    rows = []
    for r in receptions:
        rows.append([r.numero, r.commande.numero, str(r.commande.fournisseur), (r.date_validation or r.date_creation).strftime("%d/%m/%Y"), format_mga(r.montant_total)])
    numero = f"RA-{timezone.localdate():%Y%m%d}"
    date_doc = f"{date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}"
    totals = [("Total achats (réceptions validées)", format_mga(total))]
    return build_pdf("Rapport des achats", numero, date_doc, ["Réception", "Commande", "Fournisseur", "Date", "Montant (MGA)"], rows, totals=totals, col_widths=[30*mm,30*mm,45*mm,25*mm,40*mm])


def pdf_produits_peremption(lots, jours):
    rows = []
    for lot in lots:
        rows.append([str(lot.medicament), lot.numero_lot, lot.date_peremption.strftime("%d/%m/%Y"), str(lot.quantite_disponible)])
    numero = f"PER-{timezone.localdate():%Y%m%d}"
    date_doc = timezone.localdate().strftime("%d/%m/%Y")
    extra = [f"Horizon : {jours} jours"]
    return build_pdf("Produits proches de la péremption", numero, date_doc, ["Médicament", "Lot", "Péremption", "Qté dispo"], rows, extra_lines=extra, col_widths=[80*mm,30*mm,30*mm,30*mm])
