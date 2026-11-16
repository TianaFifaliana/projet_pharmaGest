from django.urls import path

from . import views

app_name = "fournisseurs"

urlpatterns = [
    path("", views.ListeFournisseursView.as_view(), name="liste"),
    path("creer/", views.CreationFournisseurView.as_view(), name="creation"),
    path("<int:pk>/", views.DetailFournisseurView.as_view(), name="detail"),
    path(
        "<int:pk>/modifier/",
        views.ModificationFournisseurView.as_view(),
        name="modification",
    ),
    path("<int:pk>/activer/", views.activer_fournisseur, name="activer"),
    path("<int:pk>/desactiver/", views.desactiver_fournisseur, name="desactiver"),
    path(
        "<int:pk>/supprimer/",
        views.SuppressionFournisseurView.as_view(),
        name="suppression",
    ),
]
