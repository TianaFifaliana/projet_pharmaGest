from django.urls import path

from . import views

app_name = "achats"

urlpatterns = [
    path("", views.ListeCommandesAchatView.as_view(), name="liste"),
    path("creer/", views.CreationCommandeAchatView.as_view(), name="creation"),
    path("<int:pk>/", views.DetailCommandeAchatView.as_view(), name="detail"),
    path("<int:pk>/modifier/", views.ModificationCommandeAchatView.as_view(), name="modification"),
    path("<int:pk>/<str:action>/", views.CommandeStatutActionView.as_view(), name="action_statut"),
    path("<int:pk>/reception/", views.ReceptionCommandeView.as_view(), name="reception"),
    path("receptions/<int:pk>/", views.DetailReceptionView.as_view(), name="reception_detail"),
]
