"""URLs de la app tournament."""

from django.urls import path

from . import views

app_name = "tournament"

urlpatterns = [
    path("resultados/", views.results, name="results"),
]
