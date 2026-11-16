from django.urls import path

from . import views

app_name = "clients"

urlpatterns = [
    path("", views.ListeClientsView.as_view(), name="liste"),
    path("creer/", views.CreationClientView.as_view(), name="creation"),
    path("<int:pk>/", views.DetailClientView.as_view(), name="detail"),
    path(
        "<int:pk>/modifier/",
        views.ModificationClientView.as_view(),
        name="modification",
    ),
    path("<int:pk>/activer/", views.activer_client, name="activer"),
    path("<int:pk>/desactiver/", views.desactiver_client, name="desactiver"),
    path(
        "<int:pk>/supprimer/",
        views.SuppressionClientView.as_view(),
        name="suppression",
    ),
]
