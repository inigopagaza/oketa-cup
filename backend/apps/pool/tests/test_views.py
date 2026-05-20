"""
Tests de las vistas de la app pool.

Cubre el flujo de selección de equipos:
- dashboard: redirección según estado de confirmación
- select_teams: formulario de selección
- confirm_selection: validación de presupuesto y bloqueo de selección
"""

import pytest
from django.urls import reverse

from apps.pool.models import Participant
from apps.tournament.models import NationalTeam

# ── Fixtures locales ──────────────────────────────────────────────────────────


@pytest.fixture
def user_bob(db):
    """Usuario sin confirmación de selección."""
    from apps.accounts.models import User

    return User.objects.create_user(username="bob_views", password="testpass123")


@pytest.fixture
def team_cheap(db):
    """Selección de precio bajo (10 monedas)."""
    return NationalTeam.objects.create(
        name="Baratos FC", code="BAR", flag_emoji="🏳️", group="A", price=10
    )


@pytest.fixture
def team_expensive(db):
    """Selección de precio muy alto (200 monedas)."""
    return NationalTeam.objects.create(
        name="Caros FC", code="CAR", flag_emoji="🏴", group="B", price=200
    )


@pytest.fixture
def team_expensive2(db):
    """Segunda selección cara (100 monedas)."""
    return NationalTeam.objects.create(
        name="Caros2 FC", code="CR2", flag_emoji="🚩", group="C", price=100
    )


# ── Dashboard ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDashboardView:
    """Tests de la vista dashboard."""

    URL = "pool:dashboard"

    def test_redirige_si_no_autenticado(self, client):
        resp = client.get(reverse(self.URL))
        assert resp.status_code == 302
        assert "/login/" in resp["Location"]

    def test_redirige_a_seleccion_si_no_confirmado(self, client, user_bob):
        client.force_login(user_bob)
        resp = client.get(reverse(self.URL))
        assert resp.status_code == 302
        assert reverse("pool:select_teams") in resp["Location"]

    def test_muestra_dashboard_si_confirmado(self, client, user_bob, tournament_config):
        user_bob.has_confirmed_selection = True
        user_bob.save()
        Participant.objects.create(user=user_bob)
        client.force_login(user_bob)
        resp = client.get(reverse(self.URL))
        assert resp.status_code == 200


# ── Selección de equipos ──────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSelectTeamsView:
    """Tests de la vista de selección de equipos."""

    URL = "pool:select_teams"

    def test_redirige_si_no_autenticado(self, client):
        resp = client.get(reverse(self.URL))
        assert resp.status_code == 302
        assert "/login/" in resp["Location"]

    def test_muestra_formulario_si_no_confirmado(
        self, client, user_bob, tournament_config
    ):
        client.force_login(user_bob)
        resp = client.get(reverse(self.URL))
        assert resp.status_code == 200

    def test_redirige_a_dashboard_si_ya_confirmado(self, client, user_bob):
        user_bob.has_confirmed_selection = True
        user_bob.save()
        client.force_login(user_bob)
        resp = client.get(reverse(self.URL))
        assert resp.status_code == 302
        assert reverse("pool:dashboard") in resp["Location"]

    def test_contexto_incluye_equipos_y_presupuesto(
        self, client, user_bob, team_cheap, tournament_config
    ):
        client.force_login(user_bob)
        resp = client.get(reverse(self.URL))
        assert "teams" in resp.context
        assert "budget" in resp.context
        assert resp.context["budget"] == 220


# ── Confirmación de selección ─────────────────────────────────────────────────


@pytest.mark.django_db
class TestConfirmSelectionView:
    """Tests de la vista de confirmación de selección."""

    URL = "pool:confirm_selection"

    def test_redirige_si_no_autenticado(self, client, team_cheap):
        resp = client.post(reverse(self.URL), {"teams": [str(team_cheap.id)]})
        assert resp.status_code == 302
        assert "/login/" in resp["Location"]

    def test_confirmar_seleccion_valida(
        self, client, user_bob, team_cheap, tournament_config
    ):
        """Presupuesto dentro del límite → confirma y redirige al dashboard."""
        client.force_login(user_bob)
        resp = client.post(
            reverse(self.URL),
            {"teams": [str(team_cheap.id)]},
        )
        assert resp.status_code == 302
        assert reverse("pool:dashboard") in resp["Location"]

        user_bob.refresh_from_db()
        assert user_bob.has_confirmed_selection is True

        participant = Participant.objects.get(user=user_bob)
        assert participant.teams.count() == 1
        assert participant.teams.first() == team_cheap

    def test_presupuesto_superado_muestra_error(
        self, client, user_bob, team_expensive, team_expensive2, tournament_config
    ):
        """expensive(200) + expensive2(100) = 300 > 220 → rechaza con error."""
        client.force_login(user_bob)
        resp = client.post(
            reverse(self.URL),
            {"teams": [str(team_expensive.id), str(team_expensive2.id)]},
        )
        assert resp.status_code == 200
        assert "error" in resp.context

        user_bob.refresh_from_db()
        assert user_bob.has_confirmed_selection is False

    def test_ya_confirmado_redirige_sin_cambios(
        self, client, user_bob, team_cheap, tournament_config
    ):
        """Si ya confirmó, no se vuelven a aplicar cambios."""
        user_bob.has_confirmed_selection = True
        user_bob.save()
        client.force_login(user_bob)
        resp = client.post(
            reverse(self.URL),
            {"teams": [str(team_cheap.id)]},
        )
        assert resp.status_code == 302
        assert reverse("pool:dashboard") in resp["Location"]
        # No se crea un Participant nuevo (no hay Participant en BD para este usuario)
        assert not Participant.objects.filter(user=user_bob).exists()

    def test_guarda_predicciones_individuales(
        self, client, user_bob, team_cheap, tournament_config
    ):
        """Los campos de predicción se guardan junto con la selección."""
        client.force_login(user_bob)
        resp = client.post(
            reverse(self.URL),
            {
                "teams": [str(team_cheap.id)],
                "predicted_mvp": "Messi",
                "predicted_top_scorer": "Mbappé",
                "predicted_best_goalkeeper": "Ter Stegen",
            },
        )
        assert resp.status_code == 302
        participant = Participant.objects.get(user=user_bob)
        assert participant.predicted_mvp == "Messi"
        assert participant.predicted_top_scorer == "Mbappé"
        assert participant.predicted_best_goalkeeper == "Ter Stegen"
