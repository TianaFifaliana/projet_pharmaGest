from django.contrib import admin

from .models import LigneVente, Paiement, RetourVente, Vente


class LigneVenteInline(admin.TabularInline):
    model = LigneVente
    extra = 0
    autocomplete_fields = ("lot",)
    fields = ("lot", "quantite", "prix_applique")


@admin.register(Vente)
class VenteAdmin(admin.ModelAdmin):
    list_display = (
        "numero",
        "client",
        "statut",
        "auteur",
        "montant_total_affiche",
        "date_creation",
    )
    list_filter = ("statut", "date_creation")
    search_fields = ("numero", "client__nom", "client__prenom", "auteur__username")
    list_select_related = ("client", "auteur")
    date_hierarchy = "date_creation"
    readonly_fields = ("numero", "statut", "auteur", "date_validation", "date_creation")
    autocomplete_fields = ("client",)
    inlines = (LigneVenteInline,)

    @admin.display(description="Montant total")
    def montant_total_affiche(self, obj):
        return f"{obj.montant_total:.2f} Ar"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.auteur = request.user
        super().save_model(request, obj, form, change)


@admin.register(LigneVente)
class LigneVenteAdmin(admin.ModelAdmin):
    list_display = ("vente", "lot", "quantite", "prix_applique", "total_ligne")
    list_filter = ("vente__statut",)
    search_fields = (
        "vente__numero",
        "lot__numero_lot",
        "lot__medicament__nom_commercial",
    )
    list_select_related = ("vente", "lot", "lot__medicament")
    autocomplete_fields = ("vente", "lot")


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ("vente", "mode", "statut", "montant", "auteur", "date_paiement")
    list_filter = ("mode", "statut", "date_paiement")
    search_fields = ("vente__numero", "auteur__username")
    list_select_related = ("vente", "auteur")
    date_hierarchy = "date_paiement"
    readonly_fields = ("auteur", "date_paiement")
    autocomplete_fields = ("vente",)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.auteur = request.user
        super().save_model(request, obj, form, change)


@admin.register(RetourVente)
class RetourVenteAdmin(admin.ModelAdmin):
    list_display = ("vente", "montant", "auteur", "date_creation")
    list_filter = ("date_creation",)
    search_fields = ("vente__numero", "motif", "auteur__username")
    list_select_related = ("vente", "auteur")
    date_hierarchy = "date_creation"
    readonly_fields = ("auteur", "date_creation")
    autocomplete_fields = ("vente",)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.auteur = request.user
        super().save_model(request, obj, form, change)
