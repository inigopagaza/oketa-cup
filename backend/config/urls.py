"""URL configuration raíz del proyecto OketaCup."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Admin Django nativo (gestión interna)
    path("django-admin/", admin.site.urls),
    # API REST (Fase 3)
    # path("api/", include("apps.api.urls")),
    # Frontend Django templates
    path("", include("apps.accounts.urls")),
    path("pool/", include("apps.pool.urls")),
    path("tournament/", include("apps.tournament.urls")),
]
