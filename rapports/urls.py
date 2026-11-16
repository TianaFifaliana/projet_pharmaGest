from django.urls import path

from . import pdf_views
from .views import TableauBordView

app_name = "rapports"

urlpatterns = [
    path("", TableauBordView.as_view(), name="tableau_bord"),
    path("pdf/ventes/<int:pk>/recu/", pdf_views.recu_vente_pdf, name="pdf_recu_vente"),
    path("pdf/ventes/<int:pk>/facture/", pdf_views.facture_vente_pdf, name="pdf_facture_vente"),
    path("pdf/achats/commandes/<int:pk>/", pdf_views.bon_commande_pdf, name="pdf_bon_commande"),
    path("pdf/achats/receptions/<int:pk>/", pdf_views.bon_reception_pdf, name="pdf_bon_reception"),
    path("pdf/stock/", pdf_views.rapport_stock_pdf, name="pdf_rapport_stock"),
    path("pdf/ventes/", pdf_views.rapport_ventes_pdf, name="pdf_rapport_ventes"),
    path("pdf/achats/", pdf_views.rapport_achats_pdf, name="pdf_rapport_achats"),
    path("pdf/peremption/", pdf_views.produits_peremption_pdf, name="pdf_produits_peremption"),
]
