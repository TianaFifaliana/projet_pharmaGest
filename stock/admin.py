from django.contrib import admin

from .models import LotStock, MouvementStock


@admin.register(LotStock)
class LotStockAdmin(admin.ModelAdmin):
    list_display = (
        "medicament",
        "numero_lot",
        "date_peremption",
        "quantite_recue",
        "quantite_disponible",
        "bloque",
        "est_perime",
        "est_vendable",
        "date_reception",
    )
    list_filter = ("bloque", "date_peremption", "medicament__categorie")
    search_fields = (
        "numero_lot",
        "medicament__nom_commercial",
        "medicament__nom_generique",
    )
    list_select_related = ("medicament",)
    date_hierarchy = "date_peremption"
    autocomplete_fields = ("medicament",)

    @admin.display(boolean=True, description="Périmé")
    def est_perime(self, obj):
        return obj.est_perime

    @admin.display(boolean=True, description="Vendable")
    def est_vendable(self, obj):
        return obj.est_vendable


@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):
    list_display = (
        "date_mouvement",
        "type_mouvement",
        "lot",
        "quantite",
        "auteur",
        "reference",
    )
    list_filter = ("type_mouvement", "date_mouvement")
    search_fields = (
        "lot__numero_lot",
        "lot__medicament__nom_commercial",
        "reference",
        "auteur__username",
    )
    list_select_related = ("lot", "lot__medicament", "auteur")
    date_hierarchy = "date_mouvement"
    readonly_fields = (
        "type_mouvement",
        "quantite",
        "lot",
        "auteur",
        "date_mouvement",
        "reference",
        "commentaire",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
