"""Admin de accounts."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Admin extendido para el modelo User personalizado."""

    list_display = (
        "username",
        "email",
        "preferred_language",
        "has_confirmed_selection",
        "is_staff",
    )
    list_filter = ("preferred_language", "has_confirmed_selection", "is_staff")
    fieldsets = UserAdmin.fieldsets + (  # type: ignore[operator]
        (
            "OketaCup",
            {"fields": ("preferred_language", "has_confirmed_selection")},
        ),
    )
