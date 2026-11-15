"""Routage principal du projet PharmaGest."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from utilisateurs.views import AccueilView

urlpatterns = [
    path("", AccueilView.as_view(), name="accueil"),
    path("admin/", admin.site.urls),
    path("utilisateurs/", include("utilisateurs.urls")),
]

handler403 = "utilisateurs.views.erreur_403"

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
