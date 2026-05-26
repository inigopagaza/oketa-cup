"""URL configuration raíz del proyecto OketaCup."""

from django.contrib import admin
from django.urls import include, path

from apps.accounts.views import set_language_view

urlpatterns = [
    # Cambio de idioma (es/eu) — persiste en sesión y en el perfil del usuario
    path("i18n/set_language/", set_language_view, name="set_language"),
    # Admin Django nativo (gestión interna)
    path("django-admin/", admin.site.urls),
    # API REST (Fase 3)
    # path("api/", include("apps.api.urls")),
    # Frontend Django templates
    path("", include("apps.accounts.urls")),
    path("pool/", include("apps.pool.urls")),
    path("tournament/", include("apps.tournament.urls")),
]
