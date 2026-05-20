"""URLs de la app tournament."""

from django.urls import path

from . import views

app_name = "tournament"

urlpatterns = [
    path("resultados/", views.results, name="results"),
    path(
        "admin/resultado/<int:match_id>/",
        views.admin_set_result,
        name="admin_set_result",
    ),
    path("admin/recalcular/", views.admin_recalculate, name="admin_recalculate"),
]
