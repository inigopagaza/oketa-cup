"""URLs de la app pool."""

from django.urls import path

from . import views

app_name = "pool"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("seleccionar/", views.select_teams, name="select_teams"),
    path("seleccionar/confirmar/", views.confirm_selection, name="confirm_selection"),
]
