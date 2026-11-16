from django.contrib import admin

from .models import JournalAudit, Parametres


@admin.register(JournalAudit)
class JournalAuditAdmin(admin.ModelAdmin):
    list_display = (
        "date_action",
        "utilisateur",
        "action",
        "modele",
        "objet_id",
        "adresse_ip",
    )
    list_filter = ("action", "modele", "date_action")
    search_fields = (
        "utilisateur__username",
        "modele",
        "objet_id",
        "description",
    )
    list_select_related = ("utilisateur",)
    date_hierarchy = "date_action"
    readonly_fields = (
        "utilisateur",
        "action",
        "modele",
        "objet_id",
        "description",
        "adresse_ip",
        "date_action",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Parametres)
class ParametresAdmin(admin.ModelAdmin):
    list_display = ("nom_pharmacie", "telephone", "nif", "stat", "date_modification")

    def has_add_permission(self, request):
        if Parametres.objects.exists():
            return False
        return super().has_add_permission(request)
