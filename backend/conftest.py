"""
Configuración global de pytest para OketaCup.

Define fixtures reutilizables en todos los tests del proyecto.
Las factories de factory-boy generan datos de prueba sin depender
de fixtures de base de datos estáticas.
"""

import pytest

from apps.accounts.models import User
from apps.pool.models import Participant
from apps.tournament.models import Match, NationalTeam, TournamentConfig


@pytest.fixture
def tournament_config(db) -> TournamentConfig:
    """Configuración del torneo con presupuesto estándar."""
    return TournamentConfig.get()


@pytest.fixture
def team_argentina(db) -> NationalTeam:
    """Selección de Argentina (precio 70)."""
    return NationalTeam.objects.create(
        name="Argentina", code="ARG", flag_emoji="🇦🇷", group="A", price=70
    )


@pytest.fixture
def team_brasil(db) -> NationalTeam:
    """Selección de Brasil (precio 67)."""
    return NationalTeam.objects.create(
        name="Brasil", code="BRA", flag_emoji="🇧🇷", group="B", price=67
    )


@pytest.fixture
def team_haiti(db) -> NationalTeam:
    """Selección de Haití (precio 6, la más barata)."""
    return NationalTeam.objects.create(
        name="Haití", code="HAI", flag_emoji="🇭🇹", group="C", price=6
    )


@pytest.fixture
def user_alice(db) -> User:
    """Usuario participante de prueba."""
    return User.objects.create_user(username="alice", password="testpass123")


@pytest.fixture
def participant_alice(db, user_alice, team_argentina) -> Participant:
    """Participante con Argentina en su selección."""
    participant = Participant.objects.create(user=user_alice)
    participant.teams.add(team_argentina)
    return participant


@pytest.fixture
def finished_match_arg_bra(db, team_argentina, team_brasil) -> Match:
    """Partido Argentina 2-1 Brasil (victoria Argentina) ya finalizado."""
    from django.utils import timezone

    return Match.objects.create(
        home_team=team_argentina,
        away_team=team_brasil,
        phase=Match.Phase.GROUP,
        group="A",
        scheduled_at=timezone.now(),
        home_score=2,
        away_score=1,
        is_finished=True,
    )
