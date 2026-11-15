from django.contrib import admin

from .models import Categorie, Medicament


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ("nom", "nombre_medicaments", "date_creation")
    search_fields = ("nom", "description")
    readonly_fields = ("date_creation",)

    @admin.display(description="Médicaments")
    def nombre_medicaments(self, obj):
        return obj.medicaments.count()


@admin.register(Medicament)
class MedicamentAdmin(admin.ModelAdmin):
    list_display = (
        "nom_commercial",
        "nom_generique",
        "categorie",
        "forme",
        "dosage",
        "prix_vente",
        "seuil_alerte",
        "statut",
        "date_creation",
    )
    list_filter = ("statut", "forme", "categorie")
    search_fields = (
        "nom_commercial",
        "nom_generique",
        "code_barres",
        "laboratoire",
    )
    readonly_fields = ("date_creation", "date_modification")
    list_select_related = ("categorie",)
    fieldsets = (
        (
            "Identification",
            {
                "fields": (
                    "nom_commercial",
                    "nom_generique",
                    "code_barres",
                    "categorie",
                    "laboratoire",
                )
            },
        ),
        ("Présentation", {"fields": ("forme", "dosage", "photo")}),
        ("Prix et seuils", {"fields": ("prix_achat", "prix_vente", "seuil_alerte")}),
        (
            "Suivi",
            {"fields": ("statut", "date_creation", "date_modification")},
        ),
    )
