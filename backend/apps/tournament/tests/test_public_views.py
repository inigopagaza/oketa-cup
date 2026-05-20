"""
Tests de las vistas públicas Grupos y Eliminatorias.
"""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.tournament.models import Match, NationalTeam

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def user(db):
    u = User.objects.create_user(username="user_pub", password="testpass123")
    u.has_confirmed_selection = True
    u.save()
    return u


@pytest.fixture
def group_teams(db):
    teams = []
    for code, name in [
        ("TSA", "Test A1"),
        ("TSB", "Test A2"),
        ("TSC", "Test A3"),
        ("TSD", "Test A4"),
    ]:
        teams.append(
            NationalTeam.objects.create(
                name=name, code=code, flag_emoji="🏳️", group="A", price=10
            )
        )
    return teams


@pytest.fixture
def group_match(db, group_teams):
    t1, t2 = group_teams[0], group_teams[1]
    return Match.objects.create(
        phase=Match.Phase.GROUP,
        group="A",
        home_team=t1,
        away_team=t2,
        scheduled_at=timezone.now(),
        home_score=1,
        away_score=0,
        is_finished=True,
    )


@pytest.fixture
def ko_matches(db):
    """Crea partidos R32, R16, QF, SF, Final y 3PL mínimos."""
    now = timezone.now()
    r32 = [
        Match.objects.create(
            phase=Match.Phase.ROUND_OF_32, match_label=f"R32-{i}", scheduled_at=now
        )
        for i in range(16)
    ]
    r16 = [
        Match.objects.create(
            phase=Match.Phase.ROUND_OF_16, match_label=f"R16-{i}", scheduled_at=now
        )
        for i in range(8)
    ]
    qf = [
        Match.objects.create(
            phase=Match.Phase.QUARTER_FINAL, match_label=f"QF-{i}", scheduled_at=now
        )
        for i in range(4)
    ]
    sf = [
        Match.objects.create(
            phase=Match.Phase.SEMI_FINAL, match_label=f"SF-{i}", scheduled_at=now
        )
        for i in range(2)
    ]
    final = Match.objects.create(
        phase=Match.Phase.FINAL, match_label="Final", scheduled_at=now
    )
    third = Match.objects.create(
        phase=Match.Phase.THIRD_PLACE, match_label="3er puesto", scheduled_at=now
    )
    return {"r32": r32, "r16": r16, "qf": qf, "sf": sf, "final": final, "third": third}


# ── Vista: grupos ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGruposView:
    URL = "tournament:grupos"

    def test_accesible_sin_autenticar(self, client):
        resp = client.get(reverse(self.URL))
        assert resp.status_code == 200

    def test_accesible_autenticado(self, client, user):
        client.force_login(user)
        resp = client.get(reverse(self.URL))
        assert resp.status_code == 200

    def test_sin_grupos_muestra_pagina(self, client):
        resp = client.get(reverse(self.URL))
        assert resp.status_code == 200

    def test_con_equipos_incluye_clasificacion(self, client, group_teams, group_match):
        resp = client.get(reverse(self.URL))
        assert resp.status_code == 200
        groups_data = resp.context["groups_data"]
        assert len(groups_data) == 1
        group = groups_data[0]
        assert group["letter"] == "A"
        assert len(group["standings"]) == 4
        # El equipo con victoria aparece primero (3 pts)
        assert group["standings"][0]["pts"] == 3

    def test_clasificacion_diferencia_goles(self, client, group_teams, group_match):
        resp = client.get(reverse(self.URL))
        standings = resp.context["groups_data"][0]["standings"]
        winner = standings[0]
        loser = standings[-1]
        assert winner["dg"] > 0
        assert loser["dg"] < 0

    def test_partidos_del_grupo_incluidos(self, client, group_teams, group_match):
        resp = client.get(reverse(self.URL))
        # La vista ya no devuelve matches en el contexto, solo standings
        group = resp.context["groups_data"][0]
        assert "standings" in group
        assert len(group["standings"]) == 4


# ── Vista: eliminatorias ──────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEliminatoriasView:
    URL = "tournament:eliminatorias"

    def test_accesible_sin_autenticar(self, client):
        resp = client.get(reverse(self.URL))
        assert resp.status_code == 200

    def test_accesible_autenticado(self, client, user):
        client.force_login(user)
        resp = client.get(reverse(self.URL))
        assert resp.status_code == 200

    def test_sin_partidos_muestra_pagina(self, client):
        resp = client.get(reverse(self.URL))
        assert resp.status_code == 200

    def test_con_partidos_ko_contexto_correcto(self, client, ko_matches):
        resp = client.get(reverse(self.URL))
        assert resp.status_code == 200
        ctx = resp.context
        assert len(ctx["r32"]) == 16
        assert len(ctx["r16"]) == 8
        assert len(ctx["qf"]) == 4
        assert len(ctx["sf"]) == 2
        assert ctx["final"] is not None
        assert ctx["third"] is not None

    def test_bracket_ready_false_sin_configurar(self, client, ko_matches):
        resp = client.get(reverse(self.URL))
        assert resp.context["bracket_ready"] is False

    def test_bracket_ready_true_con_next_match(self, client, ko_matches):
        r32 = ko_matches["r32"]
        r16 = ko_matches["r16"]
        r32[0].next_match = r16[0]
        r32[0].next_match_slot = "home"
        r32[0].save()
        resp = client.get(reverse(self.URL))
        assert resp.context["bracket_ready"] is True
