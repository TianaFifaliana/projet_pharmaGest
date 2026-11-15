from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "first_name",
        "last_name",
        "email",
        "telephone",
        "is_active",
        "is_staff",
    )
    search_fields = ("username", "first_name", "last_name", "email", "telephone")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Coordonnées", {"fields": ("telephone",)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "Coordonnées",
            {"fields": ("first_name", "last_name", "email", "telephone")},
        ),
    )
