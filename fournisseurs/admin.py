from django.contrib import admin

from .models import Fournisseur


@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display = (
        "nom",
        "contact",
        "telephone",
        "email",
        "ville",
        "actif",
        "date_creation",
    )
    list_filter = ("actif", "ville")
    search_fields = ("nom", "contact", "telephone", "email", "ville")
    readonly_fields = ("date_creation",)
