"""
Tests de las vistas de gestión (tournament app).

Cubre:
- Vista gestion: acceso solo staff, contenido del contexto
- Vista gestion_set_r32_teams: asignación de equipos a R32
- Signal propagate_match_winner: propagación de ganadores en bracket
"""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.tournament.models import Match, NationalTeam

# ── Fixtures locales ──────────────────────────────────────────────────────────


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="admin_gestion", password="testpass123", is_staff=True
    )


@pytest.fixture
def normal_user(db):
    u = User.objects.create_user(username="normal_gestion", password="testpass123")
    u.has_confirmed_selection = True
    u.save()
    return u


@pytest.fixture
def team_a(db):
    return NationalTeam.objects.create(
        name="Equipo A", code="EQA", flag_emoji="🏳️", group="A", price=10
    )


@pytest.fixture
def team_b(db):
    return NationalTeam.objects.create(
        name="Equipo B", code="EQB", flag_emoji="🏴", group="B", price=10
    )


@pytest.fixture
def r32_match(db):
    """Partido de dieciseisavos sin equipos asignados."""
    return Match.objects.create(
        phase=Match.Phase.ROUND_OF_32,
        match_label="1A vs 2B",
        scheduled_at=timezone.now(),
    )


@pytest.fixture
def r16_match(db):
    """Partido de octavos (destino del bracket)."""
    return Match.objects.create(
        phase=Match.Phase.ROUND_OF_16,
        match_label="G(R32) vs G(R32)",
        scheduled_at=timezone.now(),
    )


# ── Vista: gestion ────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGestionView:
    URL = "tournament:gestion"

    def test_redirige_si_no_autenticado(self, client):
        resp = client.get(reverse(self.URL))
        assert resp.status_code == 302
        assert "/login/" in resp["Location"]

    def test_redirige_si_no_es_staff(self, client, normal_user):
        client.force_login(normal_user)
        resp = client.get(reverse(self.URL))
        assert resp.status_code == 302
        assert reverse("pool:dashboard") in resp["Location"]

    def test_staff_puede_acceder(self, client, staff_user, tournament_config):
        client.force_login(staff_user)
        resp = client.get(reverse(self.URL))
        assert resp.status_code == 200

    def test_contexto_contiene_pending_matches(
        self, client, staff_user, tournament_config, team_a, team_b
    ):
        """Partidos pasados sin resultado deben aparecer en pending_matches."""
        from datetime import timedelta

        past = timezone.now() - timedelta(hours=2)
        Match.objects.create(
            home_team=team_a,
            away_team=team_b,
            phase=Match.Phase.GROUP,
            group="A",
            scheduled_at=past,
            is_finished=False,
        )
        client.force_login(staff_user)
        resp = client.get(reverse(self.URL))
        assert resp.status_code == 200
        assert resp.context["pending_matches"].count() >= 1

    def test_contexto_contiene_r32_matches(
        self, client, staff_user, tournament_config, r32_match
    ):
        client.force_login(staff_user)
        resp = client.get(reverse(self.URL))
        assert resp.status_code == 200
        assert r32_match in resp.context["r32_matches"]

    def test_filtro_fecha_finished_matches(self, client, staff_user, tournament_config):
        """El parámetro ?fecha filtra los partidos finalizados."""
        client.force_login(staff_user)
        resp = client.get(reverse(self.URL) + "?fecha=2026-06-15")
        assert resp.status_code == 200
        import datetime

        assert resp.context["finished_matches_date"] == datetime.date(2026, 6, 15)

    def test_fecha_invalida_usa_hoy(self, client, staff_user, tournament_config):
        client.force_login(staff_user)
        resp = client.get(reverse(self.URL) + "?fecha=not-a-date")
        assert resp.status_code == 200
        assert resp.context["finished_matches_date"] == timezone.now().date()


# ── Vista: gestion_set_r32_teams ─────────────────────────────────────────────


@pytest.mark.django_db
class TestGestionSetR32Teams:
    URL = "tournament:gestion_set_r32_teams"

    def test_no_staff_redirige(self, client, normal_user, r32_match):
        client.force_login(normal_user)
        resp = client.post(
            reverse(self.URL, args=[r32_match.pk]),
            {"home_team_id": "", "away_team_id": ""},
        )
        assert resp.status_code == 302
        assert reverse("pool:dashboard") in resp["Location"]

    def test_asigna_equipos(self, client, staff_user, r32_match, team_a, team_b):
        client.force_login(staff_user)
        resp = client.post(
            reverse(self.URL, args=[r32_match.pk]),
            {"home_team_id": str(team_a.pk), "away_team_id": str(team_b.pk)},
        )
        assert resp.status_code == 302
        r32_match.refresh_from_db()
        assert r32_match.home_team == team_a
        assert r32_match.away_team == team_b

    def test_404_si_no_es_r32(self, client, staff_user, r16_match, team_a, team_b):
        """Solo partidos R32 son editables con esta vista."""
        client.force_login(staff_user)
        resp = client.post(
            reverse(self.URL, args=[r16_match.pk]),
            {"home_team_id": str(team_a.pk), "away_team_id": str(team_b.pk)},
        )
        assert resp.status_code == 404

    def test_id_invalido_no_asigna(self, client, staff_user, r32_match):
        """IDs no numéricos no deben causar error ni asignar nada."""
        client.force_login(staff_user)
        resp = client.post(
            reverse(self.URL, args=[r32_match.pk]),
            {"home_team_id": "abc", "away_team_id": "xyz"},
        )
        assert resp.status_code == 302
        r32_match.refresh_from_db()
        assert r32_match.home_team is None
        assert r32_match.away_team is None


# ── Signal: propagate_match_winner ────────────────────────────────────────────


@pytest.mark.django_db
class TestPropagateBracketSignal:
    def test_ganador_se_propaga_al_siguiente_partido(
        self, team_a, team_b, r32_match, r16_match
    ):
        """Al finalizar un R32 con ganador, el equipo pasa al siguiente slot."""
        r32_match.home_team = team_a
        r32_match.away_team = team_b
        r32_match.next_match = r16_match
        r32_match.next_match_slot = "home"
        r32_match.save()

        # Finalizar con victoria de local (team_a)
        r32_match.home_score = 2
        r32_match.away_score = 0
        r32_match.is_finished = True
        r32_match.save()

        r16_match.refresh_from_db()
        assert r16_match.home_team == team_a

    def test_empate_no_propaga(self, team_a, team_b, r32_match, r16_match):
        """Si el resultado es empate no se propaga (penal no registrado)."""
        r32_match.home_team = team_a
        r32_match.away_team = team_b
        r32_match.next_match = r16_match
        r32_match.next_match_slot = "home"
        r32_match.save()

        r32_match.home_score = 1
        r32_match.away_score = 1
        r32_match.is_finished = True
        r32_match.save()

        r16_match.refresh_from_db()
        assert r16_match.home_team is None

    def test_grupo_no_propaga(self, team_a, team_b, r16_match):
        """Partidos de grupos no activan propagación de bracket."""
        group_match = Match.objects.create(
            home_team=team_a,
            away_team=team_b,
            phase=Match.Phase.GROUP,
            group="A",
            next_match=r16_match,
            next_match_slot="home",
            scheduled_at=timezone.now(),
        )
        group_match.home_score = 2
        group_match.away_score = 0
        group_match.is_finished = True
        group_match.save()

        r16_match.refresh_from_db()
        assert r16_match.home_team is None

    def test_sin_next_match_no_falla(self, team_a, team_b, r32_match):
        """Si no hay next_match configurado, el signal no lanza excepción."""
        r32_match.home_team = team_a
        r32_match.away_team = team_b
        r32_match.home_score = 3
        r32_match.away_score = 1
        r32_match.is_finished = True
        r32_match.save()  # No debe lanzar excepción

    def test_visitante_gana_va_al_slot_away(self, team_a, team_b, r32_match, r16_match):
        """El visitante ganador va al slot 'away' del siguiente partido."""
        r32_match.home_team = team_a
        r32_match.away_team = team_b
        r32_match.next_match = r16_match
        r32_match.next_match_slot = "away"
        r32_match.save()

        r32_match.home_score = 0
        r32_match.away_score = 3
        r32_match.is_finished = True
        r32_match.save()

        r16_match.refresh_from_db()
        assert r16_match.away_team == team_b
