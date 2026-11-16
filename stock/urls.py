from django.urls import path

from . import views

app_name = "stock"

urlpatterns = [
    path("", views.VueStockDisponibleView.as_view(), name="disponible"),
    path("mouvements/", views.HistoriqueMouvementsView.as_view(), name="mouvements"),
    path("alertes/", views.AlertesStockView.as_view(), name="alertes"),
    path("inventaire/", views.InventairePhysiqueView.as_view(), name="inventaire"),
    path("lots/<int:pk>/blocage/", views.BasculerBlocageLotView.as_view(), name="basculer_blocage"),
]
