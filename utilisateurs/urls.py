from django.urls import path

from . import views

app_name = "utilisateurs"

urlpatterns = [
    path("", views.ListeUtilisateursView.as_view(), name="liste"),
    path("connexion/", views.ConnexionView.as_view(), name="connexion"),
    path("deconnexion/", views.DeconnexionView.as_view(), name="deconnexion"),
    path(
        "mot-de-passe/",
        views.ChangementMotDePasseView.as_view(),
        name="changement_mot_de_passe",
    ),
    path(
        "mot-de-passe/termine/",
        views.ChangementMotDePasseTermineView.as_view(),
        name="changement_mot_de_passe_termine",
    ),
    path(
        "mot-de-passe/reinitialisation/",
        views.ReinitialisationMotDePasseView.as_view(),
        name="reinitialisation_mot_de_passe",
    ),
    path(
        "mot-de-passe/reinitialisation/envoyee/",
        views.ReinitialisationMotDePasseEnvoyeeView.as_view(),
        name="reinitialisation_mot_de_passe_envoyee",
    ),
    path(
        "mot-de-passe/reinitialisation/<uidb64>/<token>/",
        views.ConfirmationReinitialisationView.as_view(),
        name="reinitialisation_mot_de_passe_confirmation",
    ),
    path(
        "mot-de-passe/reinitialisation/terminee/",
        views.ReinitialisationMotDePasseTermineeView.as_view(),
        name="reinitialisation_mot_de_passe_terminee",
    ),
    path("creer/", views.CreationUtilisateurView.as_view(), name="creation"),
    path(
        "<int:pk>/modifier/",
        views.ModificationUtilisateurView.as_view(),
        name="modification",
    ),
    path("<int:pk>/activer/", views.activer_utilisateur, name="activer"),
    path("<int:pk>/desactiver/", views.desactiver_utilisateur, name="desactiver"),
]
