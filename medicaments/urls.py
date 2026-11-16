from django.urls import path

from . import views

app_name = "medicaments"

urlpatterns = [
    path("", views.ListeMedicamentsView.as_view(), name="liste"),
    path("creer/", views.CreationMedicamentView.as_view(), name="creation"),
    path(
        "categories/",
        views.ListeCategoriesView.as_view(),
        name="categories",
    ),
    path(
        "categories/creer/",
        views.CreationCategorieView.as_view(),
        name="categorie_creation",
    ),
    path(
        "categories/<int:pk>/modifier/",
        views.ModificationCategorieView.as_view(),
        name="categorie_modification",
    ),
    path(
        "categories/<int:pk>/supprimer/",
        views.SuppressionCategorieView.as_view(),
        name="categorie_suppression",
    ),
    path("<int:pk>/", views.DetailMedicamentView.as_view(), name="detail"),
    path(
        "<int:pk>/modifier/",
        views.ModificationMedicamentView.as_view(),
        name="modification",
    ),
    path(
        "<int:pk>/supprimer/",
        views.SuppressionMedicamentView.as_view(),
        name="suppression",
    ),
]
