"""URLs de la app tournament."""

from django.urls import path

from . import views

app_name = "tournament"

urlpatterns = [
    path("resultados/", views.results, name="results"),
    path("grupos/", views.grupos, name="grupos"),
    path("eliminatorias/", views.eliminatorias, name="eliminatorias"),
    path(
        "admin/resultado/<int:match_id>/",
        views.admin_set_result,
        name="admin_set_result",
    ),
    path("admin/recalcular/", views.admin_recalculate, name="admin_recalculate"),
    path("admin/premios/", views.admin_award_prizes, name="admin_award_prizes"),
    path("gestion/", views.gestion, name="gestion"),
    path(
        "gestion/dieciseisavos/<int:match_id>/",
        views.gestion_set_r32_teams,
        name="gestion_set_r32_teams",
    ),
    path(
        "gestion/configurar-bracket/",
        views.gestion_configure_bracket,
        name="gestion_configure_bracket",
    ),
]
