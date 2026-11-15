from django.contrib import admin

from .models import CommandeAchat, LigneAchat, LigneReception, ReceptionAchat


class LigneAchatInline(admin.TabularInline):
    model = LigneAchat
    extra = 0
    autocomplete_fields = ("medicament",)
    fields = ("medicament", "quantite", "prix_unitaire")


class LigneReceptionInline(admin.TabularInline):
    model = LigneReception
    extra = 0
    autocomplete_fields = ("ligne_achat", "lot")
    fields = ("ligne_achat", "quantite", "numero_lot", "date_peremption", "lot")


@admin.register(CommandeAchat)
class CommandeAchatAdmin(admin.ModelAdmin):
    list_display = (
        "numero",
        "fournisseur",
        "statut",
        "auteur",
        "montant_total_affiche",
        "date_creation",
    )
    list_filter = ("statut", "date_creation", "fournisseur")
    search_fields = ("numero", "fournisseur__nom", "auteur__username")
    list_select_related = ("fournisseur", "auteur")
    date_hierarchy = "date_creation"
    readonly_fields = ("numero", "auteur", "date_creation", "date_modification")
    autocomplete_fields = ("fournisseur",)
    inlines = (LigneAchatInline,)

    @admin.display(description="Montant total")
    def montant_total_affiche(self, obj):
        return f"{obj.montant_total:.2f} Ar"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.auteur = request.user
        super().save_model(request, obj, form, change)


@admin.register(LigneAchat)
class LigneAchatAdmin(admin.ModelAdmin):
    list_display = (
        "commande",
        "medicament",
        "quantite",
        "prix_unitaire",
        "total_ligne",
        "quantite_recue",
    )
    list_filter = ("commande__statut",)
    search_fields = (
        "commande__numero",
        "medicament__nom_commercial",
        "medicament__nom_generique",
    )
    list_select_related = ("commande", "medicament")
    autocomplete_fields = ("commande", "medicament")


@admin.register(ReceptionAchat)
class ReceptionAchatAdmin(admin.ModelAdmin):
    list_display = (
        "numero",
        "commande",
        "est_validee",
        "date_validation",
        "validee_par",
        "auteur",
        "date_creation",
    )
    list_filter = ("est_validee", "date_creation")
    search_fields = (
        "numero",
        "commande__numero",
        "commande__fournisseur__nom",
    )
    list_select_related = ("commande", "commande__fournisseur", "auteur", "validee_par")
    date_hierarchy = "date_creation"
    readonly_fields = (
        "numero",
        "est_validee",
        "date_validation",
        "validee_par",
        "auteur",
        "date_creation",
    )
    autocomplete_fields = ("commande",)
    inlines = (LigneReceptionInline,)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.auteur = request.user
        super().save_model(request, obj, form, change)


@admin.register(LigneReception)
class LigneReceptionAdmin(admin.ModelAdmin):
    list_display = (
        "reception",
        "ligne_achat",
        "quantite",
        "numero_lot",
        "date_peremption",
        "lot",
    )
    list_filter = ("reception__est_validee",)
    search_fields = (
        "reception__numero",
        "numero_lot",
        "ligne_achat__medicament__nom_commercial",
    )
    list_select_related = ("reception", "ligne_achat", "ligne_achat__medicament")
    autocomplete_fields = ("reception", "ligne_achat", "lot")
