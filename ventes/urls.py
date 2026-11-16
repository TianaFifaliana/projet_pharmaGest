from django.urls import path

from . import views

app_name = "ventes"

urlpatterns = [
    path("", views.ListeVentesView.as_view(), name="liste"),
    path("caisse/", views.CaisseVenteView.as_view(), name="caisse"),
    path("api/medicaments/", views.RechercheMedicamentsView.as_view(), name="api_medicaments"),
    path("api/medicaments/<int:medicament_id>/lots/", views.LotsMedicamentsView.as_view(), name="api_lots"),
    path("<int:pk>/", views.DetailVenteView.as_view(), name="detail"),
    path("<int:pk>/recu/", views.RecuVenteView.as_view(), name="recu"),
    path("<int:pk>/lignes/<int:ligne_id>/retour/", views.RetourLigneView.as_view(), name="retour_ligne"),
    path("<int:pk>/annuler/", views.AnnulationVenteView.as_view(), name="annuler"),
]
