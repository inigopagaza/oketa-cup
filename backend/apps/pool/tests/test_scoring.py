"""
Tests del motor de puntuación (apps/pool/services/scoring.py).

Cubre los casos principales del sistema de puntos:
- Victoria, empate y derrota en fase de grupos
- Avance de fases eliminatorias
- Campeón del Mundial
- Premios individuales (MVP, Pichichi, Zamora)
- Protección contra duplicados
- Clasificación de grupos (ADVANCE_GRP, TOP_GROUP)
"""

import pytest

from apps.pool.models import ScoreLog
from apps.pool.services.scoring import (
    POINTS_CHAMPION,
    POINTS_DRAW,
    POINTS_FINAL,
    POINTS_FIRST_IN_GROUP,
    POINTS_MVP,
    POINTS_QUALIFY_GROUP,
    POINTS_QUARTER_FINAL,
    POINTS_ROUND_OF_16,
    POINTS_SEMI_FINAL,
    POINTS_TOP_SCORER,
    POINTS_WIN,
    award_champion,
    award_individual_prizes,
    award_phase_advancement,
    process_group_completion,
    process_match_result,
)
from apps.tournament.models import Match, NationalTeam


@pytest.mark.django_db
class TestMatchScoring:
    """Tests del procesado de resultados de partido."""

    def test_victoria_otorga_tres_puntos(
        self, participant_alice, finished_match_arg_bra
    ):
        """Una victoria de Argentina debe generar +3 puntos."""
        logs = process_match_result(finished_match_arg_bra)

        # Solo Argentina ganó, así que Alice (que tiene Argentina) debe tener +3
        alice_logs = [log for log in logs if log.participant == participant_alice]
        assert len(alice_logs) == 1
        assert alice_logs[0].points_earned == POINTS_WIN

    def test_derrota_no_otorga_puntos(
        self, db, team_brasil, user_alice, finished_match_arg_bra
    ):
        """Un participante con el equipo perdedor no debe obtener puntos."""
        from apps.pool.models import Participant

        participant_bob = Participant.objects.create(
            user=__import__(
                "apps.accounts.models", fromlist=["User"]
            ).User.objects.create_user(username="bob", password="testpass123")
        )
        participant_bob.teams.add(team_brasil)

        logs = process_match_result(finished_match_arg_bra)

        bob_logs = [log for log in logs if log.participant == participant_bob]
        assert len(bob_logs) == 0

    def test_empate_otorga_un_punto(
        self, db, team_argentina, team_brasil, participant_alice
    ):
        """Un empate debe generar +1 punto."""
        from django.utils import timezone

        match = Match.objects.create(
            home_team=team_argentina,
            away_team=team_brasil,
            phase=Match.Phase.GROUP,
            group="A",
            scheduled_at=timezone.now(),
            home_score=1,
            away_score=1,
            is_finished=True,
        )

        logs = process_match_result(match)
        alice_logs = [log for log in logs if log.participant == participant_alice]

        assert len(alice_logs) == 1
        assert alice_logs[0].points_earned == POINTS_DRAW

    def test_partido_no_finalizado_no_genera_puntos(
        self, db, team_argentina, team_brasil, participant_alice
    ):
        """Un partido no finalizado no debe generar ningún ScoreLog."""
        from django.utils import timezone

        match = Match.objects.create(
            home_team=team_argentina,
            away_team=team_brasil,
            phase=Match.Phase.GROUP,
            group="A",
            scheduled_at=timezone.now(),
            is_finished=False,
        )

        logs = process_match_result(match)
        assert logs == []

    def test_no_genera_duplicados(self, participant_alice, finished_match_arg_bra):
        """Llamar a process_match_result dos veces no debe duplicar los logs."""
        process_match_result(finished_match_arg_bra)
        process_match_result(finished_match_arg_bra)

        total_logs = ScoreLog.objects.filter(match=finished_match_arg_bra).count()
        # Solo debe haber un log por equipo involucrado con participantes
        assert total_logs == 1


@pytest.mark.django_db
class TestPhaseAdvancement:
    """Tests de los puntos por avance de fases eliminatorias."""

    def test_octavos_otorga_diez_puntos(self, participant_alice, team_argentina):
        """Clasificar a octavos debe dar +10 puntos."""
        logs = award_phase_advancement(team_argentina, Match.Phase.ROUND_OF_16)
        assert len(logs) == 1
        assert logs[0].points_earned == POINTS_ROUND_OF_16

    def test_cuartos_otorga_quince_puntos(self, participant_alice, team_argentina):
        logs = award_phase_advancement(team_argentina, Match.Phase.QUARTER_FINAL)
        assert logs[0].points_earned == POINTS_QUARTER_FINAL

    def test_semis_otorga_veinte_puntos(self, participant_alice, team_argentina):
        logs = award_phase_advancement(team_argentina, Match.Phase.SEMI_FINAL)
        assert logs[0].points_earned == POINTS_SEMI_FINAL

    def test_final_otorga_veinticinco_puntos(self, participant_alice, team_argentina):
        logs = award_phase_advancement(team_argentina, Match.Phase.FINAL)
        assert logs[0].points_earned == POINTS_FINAL

    def test_campeon_otorga_veinticinco_puntos_extra(
        self, participant_alice, team_argentina
    ):
        """Ganar el Mundial añade +25 puntos además de los de la final."""
        logs = award_champion(team_argentina)
        assert len(logs) == 1
        assert logs[0].points_earned == POINTS_CHAMPION


@pytest.mark.django_db
class TestIndividualPrizes:
    """Tests de los premios individuales (MVP, Pichichi, Zamora)."""

    def test_acertar_mvp_otorga_veinte_puntos(self, participant_alice):
        """Acertar el MVP debe dar +20 puntos."""
        participant_alice.predicted_mvp = "Lionel Messi"
        participant_alice.save()

        logs = award_individual_prizes(
            real_mvp="Lionel Messi",
            real_top_scorer="",
            real_best_goalkeeper="",
        )

        assert len(logs) == 1
        assert logs[0].points_earned == POINTS_MVP

    def test_no_acertar_mvp_no_otorga_puntos(self, participant_alice):
        """No acertar el MVP no debe generar ningún log."""
        participant_alice.predicted_mvp = "Cristiano Ronaldo"
        participant_alice.save()

        logs = award_individual_prizes(
            real_mvp="Lionel Messi",
            real_top_scorer="",
            real_best_goalkeeper="",
        )

        assert logs == []

    def test_acertar_pichichi_otorga_diez_puntos(self, participant_alice):
        """Acertar el Pichichi debe dar +10 puntos."""
        participant_alice.predicted_top_scorer = "Erling Haaland"
        participant_alice.save()

        logs = award_individual_prizes(
            real_mvp="",
            real_top_scorer="Erling Haaland",
            real_best_goalkeeper="",
        )

        assert len(logs) == 1
        assert logs[0].points_earned == POINTS_TOP_SCORER


@pytest.mark.django_db
class TestParticipantTotalPoints:
    """Tests del cálculo de puntos totales del participante."""

    def test_total_points_acumula_logs(
        self, participant_alice, finished_match_arg_bra, team_argentina
    ):
        """total_points debe sumar todos los ScoreLogs del participante."""
        process_match_result(finished_match_arg_bra)
        award_phase_advancement(team_argentina, Match.Phase.ROUND_OF_16)

        assert participant_alice.total_points == POINTS_WIN + POINTS_ROUND_OF_16

    def test_total_points_sin_logs_es_cero(self, participant_alice):
        """Sin ScoreLogs, total_points debe ser 0."""
        assert participant_alice.total_points == 0


# ── Helpers para TestGroupCompletion ─────────────────────────────────────────


def _make_match(db, home, away, hs, as_, group="Z", finished=True):
    """Crea un partido de grupos y lo devuelve."""
    from django.utils import timezone

    return Match.objects.create(
        home_team=home,
        away_team=away,
        phase=Match.Phase.GROUP,
        group=group,
        scheduled_at=timezone.now(),
        home_score=hs,
        away_score=as_,
        is_finished=finished,
    )


@pytest.mark.django_db
class TestGroupCompletion:
    """Tests de la clasificación de grupos (ADVANCE_GRP y TOP_GROUP)."""

    @pytest.fixture
    def four_teams(self, db):
        """Cuatro selecciones en el grupo Z de prueba."""
        t1 = NationalTeam.objects.create(name="Alpha", code="ALP", group="Z", price=10)
        t2 = NationalTeam.objects.create(name="Beta", code="BET", group="Z", price=10)
        t3 = NationalTeam.objects.create(name="Gamma", code="GAM", group="Z", price=10)
        t4 = NationalTeam.objects.create(name="Delta", code="DEL", group="Z", price=10)
        return t1, t2, t3, t4

    @pytest.fixture
    def alice_with_alpha(self, db, four_teams):
        """Participante Alice con el equipo Alpha (1º del grupo Z)."""
        from apps.accounts.models import User
        from apps.pool.models import Participant

        user = User.objects.create_user(username="alice_z", password="testpass123")
        participant = Participant.objects.create(user=user)
        participant.teams.add(four_teams[0])  # Alpha
        return participant

    @pytest.fixture
    def bob_with_beta(self, db, four_teams):
        """Participante Bob con el equipo Beta (2º del grupo Z)."""
        from apps.accounts.models import User
        from apps.pool.models import Participant

        user = User.objects.create_user(username="bob_z", password="testpass123")
        participant = Participant.objects.create(user=user)
        participant.teams.add(four_teams[1])  # Beta
        return participant

    def _six_matches(self, db, teams, group="Z"):
        """Crea los 6 partidos del grupo con resultado fijo: Alpha gana todo."""
        t1, t2, t3, t4 = teams
        # Alpha (t1) gana los 3, Beta (t2) gana 2 contra t3 y t4
        _make_match(db, t1, t2, 1, 0, group)
        _make_match(db, t1, t3, 2, 0, group)
        _make_match(db, t1, t4, 3, 0, group)
        _make_match(db, t2, t3, 1, 0, group)
        _make_match(db, t2, t4, 1, 0, group)
        _make_match(db, t3, t4, 0, 0, group)

    def test_grupo_incompleto_no_genera_logs(self, db, four_teams, alice_with_alpha):
        """No debe calcular puntos si faltan partidos por jugar."""
        t1, t2, t3, t4 = four_teams
        # Solo 5 partidos de 6
        _make_match(db, t1, t2, 1, 0)
        _make_match(db, t1, t3, 2, 0)
        _make_match(db, t1, t4, 3, 0)
        _make_match(db, t2, t3, 1, 0)
        _make_match(db, t2, t4, 1, 0)

        logs = process_group_completion("Z")
        assert logs == []

    def test_primero_recibe_advance_y_top(
        self, db, four_teams, alice_with_alpha, bob_with_beta
    ):
        """El 1º del grupo debe recibir ADVANCE_GRP (+6) y TOP_GROUP (+2)."""
        self._six_matches(db, four_teams)
        logs = process_group_completion("Z")

        alice_logs = [lg for lg in logs if lg.participant == alice_with_alpha]
        points = {lg.points_earned for lg in alice_logs}
        assert POINTS_QUALIFY_GROUP in points
        assert POINTS_FIRST_IN_GROUP in points

    def test_segundo_recibe_advance_no_top(
        self, db, four_teams, alice_with_alpha, bob_with_beta
    ):
        """El 2º del grupo debe recibir ADVANCE_GRP (+6) pero NO TOP_GROUP."""
        self._six_matches(db, four_teams)
        logs = process_group_completion("Z")

        bob_logs = [lg for lg in logs if lg.participant == bob_with_beta]
        points = {lg.points_earned for lg in bob_logs}
        assert POINTS_QUALIFY_GROUP in points
        assert POINTS_FIRST_IN_GROUP not in points

    def test_idempotencia_no_duplica_logs(
        self, db, four_teams, alice_with_alpha, bob_with_beta
    ):
        """Llamar dos veces a process_group_completion no debe duplicar logs."""
        self._six_matches(db, four_teams)

        process_group_completion("Z")
        process_group_completion("Z")

        advance_logs = ScoreLog.objects.filter(
            reason="Clasificado desde grupo Z",
        ).count()
        # 2 participantes con equipos que clasifican (alice y bob)
        assert advance_logs == 2
