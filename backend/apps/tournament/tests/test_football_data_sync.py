"""Tests de sincronización con football-data.org."""

from datetime import UTC, datetime

import pytest

from apps.tournament.models import Match
from apps.tournament.services.football_data_sync import FootballDataSyncService


@pytest.mark.django_db
class TestFootballDataSyncService:
    @staticmethod
    def _group_stage_payload_matches(*, main_status: str = "FINISHED") -> list[dict]:
        return [
            {
                "utcDate": "2026-06-11T16:00:00Z",
                "stage": "GROUP_STAGE",
                "status": main_status,
                "group": "GROUP_A",
                "homeTeam": {"tla": "ARG"},
                "awayTeam": {"tla": "BRA"},
                "score": {
                    "winner": "HOME_TEAM",
                    "duration": "REGULAR",
                    "fullTime": {"home": 2, "away": 0},
                },
            },
            {
                "utcDate": "2026-06-12T10:00:00Z",
                "stage": "GROUP_STAGE",
                "status": "FINISHED",
                "group": "GROUP_A",
                "homeTeam": {"tla": "AAA"},
                "awayTeam": {"tla": "BBB"},
                "score": {
                    "winner": "HOME_TEAM",
                    "duration": "REGULAR",
                    "fullTime": {"home": 1, "away": 0},
                },
            },
            {
                "utcDate": "2026-06-12T13:00:00Z",
                "stage": "GROUP_STAGE",
                "status": "FINISHED",
                "group": "GROUP_A",
                "homeTeam": {"tla": "CCC"},
                "awayTeam": {"tla": "DDD"},
                "score": {
                    "winner": "HOME_TEAM",
                    "duration": "REGULAR",
                    "fullTime": {"home": 2, "away": 1},
                },
            },
            {
                "utcDate": "2026-06-13T10:00:00Z",
                "stage": "GROUP_STAGE",
                "status": "FINISHED",
                "group": "GROUP_A",
                "homeTeam": {"tla": "AAA"},
                "awayTeam": {"tla": "CCC"},
                "score": {
                    "winner": "DRAW",
                    "duration": "REGULAR",
                    "fullTime": {"home": 1, "away": 1},
                },
            },
            {
                "utcDate": "2026-06-13T13:00:00Z",
                "stage": "GROUP_STAGE",
                "status": "FINISHED",
                "group": "GROUP_A",
                "homeTeam": {"tla": "BBB"},
                "awayTeam": {"tla": "DDD"},
                "score": {
                    "winner": "AWAY_TEAM",
                    "duration": "REGULAR",
                    "fullTime": {"home": 0, "away": 2},
                },
            },
            {
                "utcDate": "2026-06-14T13:00:00Z",
                "stage": "GROUP_STAGE",
                "status": "FINISHED",
                "group": "GROUP_A",
                "homeTeam": {"tla": "AAA"},
                "awayTeam": {"tla": "DDD"},
                "score": {
                    "winner": "AWAY_TEAM",
                    "duration": "REGULAR",
                    "fullTime": {"home": 0, "away": 1},
                },
            },
        ]

    def test_knockout_penaltis_mapea_campos_y_recalcula_puntos(
        self, monkeypatch, team_argentina, team_brasil
    ):
        match = Match.objects.create(
            home_team=team_argentina,
            away_team=team_brasil,
            phase=Match.Phase.ROUND_OF_16,
            scheduled_at=datetime(2026, 7, 2, 19, 0, tzinfo=UTC),
            is_finished=False,
        )

        called_match_scores: list[int] = []

        def fake_process_match_result(arg_match):
            called_match_scores.append(arg_match.pk)
            return []

        monkeypatch.setattr(
            "apps.tournament.services.football_data_sync.process_match_result",
            fake_process_match_result,
        )
        service = FootballDataSyncService(api_key="token-test", use_api_standings=False)
        monkeypatch.setattr(
            service,
            "_fetch_matches_payload",
            lambda season=None, status=None: {
                "matches": [
                    {
                        "utcDate": "2026-07-02T19:00:00Z",
                        "stage": "LAST_16",
                        "status": "FINISHED",
                        "group": None,
                        "homeTeam": {"tla": "ARG"},
                        "awayTeam": {"tla": "BRA"},
                        "score": {
                            "winner": "HOME_TEAM",
                            "duration": "PENALTY_SHOOTOUT",
                            "fullTime": {"home": 1, "away": 1},
                        },
                    }
                ]
            },
        )

        summary = service.sync_matches()

        match.refresh_from_db()
        assert summary.updated == 1
        assert summary.scored_matches == 1
        assert match.home_score == 1
        assert match.away_score == 1
        assert match.is_finished is True
        assert match.decided_in_90 is False
        assert match.penalties_winner == Match.PenaltiesWinner.HOME
        assert called_match_scores == [match.pk]

    def test_group_stage_recalcula_grupo_desde_standings_api(
        self, monkeypatch, team_argentina, team_brasil
    ):
        match = Match.objects.create(
            home_team=team_argentina,
            away_team=team_brasil,
            phase=Match.Phase.GROUP,
            group="A",
            scheduled_at=datetime(2026, 6, 11, 16, 0, tzinfo=UTC),
            is_finished=False,
        )

        called_groups: list[str] = []
        called_local_groups: list[str] = []

        monkeypatch.setattr(
            "apps.tournament.services.football_data_sync.process_match_result",
            lambda arg_match: [],
        )

        def fake_process_group_first_from_standings(group: str, ranked_teams):
            called_groups.append(group)
            assert ranked_teams[0] == team_argentina
            assert ranked_teams[1] == team_brasil
            return []

        monkeypatch.setattr(
            "apps.tournament.services.football_data_sync.process_group_first_from_standings",
            fake_process_group_first_from_standings,
        )
        monkeypatch.setattr(
            "apps.tournament.services.football_data_sync.process_group_completion",
            lambda group: called_local_groups.append(group),
        )

        service = FootballDataSyncService(api_key="token-test")
        monkeypatch.setattr(
            service,
            "_fetch_matches_payload",
            lambda season=None, status=None: {
                "matches": self._group_stage_payload_matches(main_status="FINISHED")
            },
        )
        monkeypatch.setattr(
            service,
            "_fetch_standings_payload",
            lambda season=None: {
                "standings": [
                    {
                        "type": "TOTAL",
                        "group": "GROUP_A",
                        "table": [
                            {
                                "team": {"tla": "ARG", "name": "Argentina"},
                                "playedGames": 3,
                            },
                            {
                                "team": {"tla": "BRA", "name": "Brasil"},
                                "playedGames": 3,
                            },
                        ],
                    }
                ]
            },
        )

        summary = service.sync_matches()

        match.refresh_from_db()
        assert summary.updated == 1
        assert summary.group_recalculations == 1
        assert summary.group_recalculations_source == "api"
        assert called_groups == ["A"]
        assert called_local_groups == []
        assert match.decided_in_90 is True
        assert match.penalties_winner == ""

    def test_no_aplica_standings_api_si_no_hay_grupos_finalizados(
        self, monkeypatch, team_argentina, team_brasil
    ):
        monkeypatch.setattr(
            "apps.tournament.services.football_data_sync.process_match_result",
            lambda arg_match: [],
        )

        service = FootballDataSyncService(api_key="token-test")
        monkeypatch.setattr(
            service,
            "_fetch_matches_payload",
            lambda season=None, status=None: {"matches": []},
        )

        def fail_if_called(*args, **kwargs):
            raise AssertionError(
                "No debería consultarse standings API sin grupos finalizados"
            )

        monkeypatch.setattr(service, "_fetch_standings_payload", fail_if_called)

        summary = service.sync_matches()

        assert summary.group_recalculations == 0
        assert summary.group_recalculations_source == "none"
        assert summary.scored_matches == 0

    def test_no_recalcula_grupos_ya_finalizados_en_sync_posterior(
        self, monkeypatch, team_argentina, team_brasil
    ):
        Match.objects.create(
            home_team=team_argentina,
            away_team=team_brasil,
            phase=Match.Phase.GROUP,
            group="A",
            scheduled_at=datetime(2026, 6, 11, 16, 0, tzinfo=UTC),
            is_finished=True,
            home_score=2,
            away_score=0,
        )

        monkeypatch.setattr(
            "apps.tournament.services.football_data_sync.process_match_result",
            lambda arg_match: [],
        )

        service = FootballDataSyncService(api_key="token-test")
        monkeypatch.setattr(
            service,
            "_fetch_matches_payload",
            lambda season=None, status=None: {
                "matches": [
                    {
                        "utcDate": "2026-06-11T16:00:00Z",
                        "stage": "GROUP_STAGE",
                        "status": "FINISHED",
                        "group": "GROUP_A",
                        "homeTeam": {"tla": "ARG"},
                        "awayTeam": {"tla": "BRA"},
                        "score": {
                            "winner": "HOME_TEAM",
                            "duration": "REGULAR",
                            "fullTime": {"home": 2, "away": 0},
                        },
                    }
                ]
            },
        )

        def fail_if_called(*args, **kwargs):
            raise AssertionError(
                "No debería consultarse standings API en sync posterior sin nuevos cierres"
            )

        monkeypatch.setattr(service, "_fetch_standings_payload", fail_if_called)

        summary = service.sync_matches()

        assert summary.updated == 0
        assert summary.unchanged == 1
        assert summary.group_recalculations == 0
        assert summary.group_recalculations_source == "none"
        assert summary.scored_matches == 0

    def test_no_aplica_standings_api_si_el_grupo_no_tiene_3_partidos_por_equipo(
        self, monkeypatch, team_argentina, team_brasil
    ):
        match = Match.objects.create(
            home_team=team_argentina,
            away_team=team_brasil,
            phase=Match.Phase.GROUP,
            group="A",
            scheduled_at=datetime(2026, 6, 11, 16, 0, tzinfo=UTC),
            is_finished=False,
        )

        called_groups: list[str] = []

        monkeypatch.setattr(
            "apps.tournament.services.football_data_sync.process_match_result",
            lambda arg_match: [],
        )
        monkeypatch.setattr(
            "apps.tournament.services.football_data_sync.process_group_first_from_standings",
            lambda group, ranked_teams: called_groups.append(group),
        )

        service = FootballDataSyncService(api_key="token-test")
        monkeypatch.setattr(
            service,
            "_fetch_matches_payload",
            lambda season=None, status=None: {
                "matches": self._group_stage_payload_matches(main_status="FINISHED")
            },
        )
        monkeypatch.setattr(
            service,
            "_fetch_standings_payload",
            lambda season=None: {
                "standings": [
                    {
                        "type": "TOTAL",
                        "group": "GROUP_A",
                        "table": [
                            {
                                "team": {"tla": "ARG", "name": "Argentina"},
                                "playedGames": 2,
                            },
                            {
                                "team": {"tla": "BRA", "name": "Brasil"},
                                "playedGames": 2,
                            },
                        ],
                    }
                ]
            },
        )

        summary = service.sync_matches()

        match.refresh_from_db()
        assert summary.updated == 1
        assert summary.group_recalculations == 0
        assert summary.group_recalculations_source == "api"
        assert called_groups == []

    def test_no_aplica_standings_api_si_ultimo_partido_del_grupo_sigue_en_juego(
        self, monkeypatch, team_argentina, team_brasil
    ):
        match = Match.objects.create(
            home_team=team_argentina,
            away_team=team_brasil,
            phase=Match.Phase.GROUP,
            group="A",
            scheduled_at=datetime(2026, 6, 11, 16, 0, tzinfo=UTC),
            is_finished=False,
        )

        called_groups: list[str] = []

        monkeypatch.setattr(
            "apps.tournament.services.football_data_sync.process_match_result",
            lambda arg_match: [],
        )
        monkeypatch.setattr(
            "apps.tournament.services.football_data_sync.process_group_first_from_standings",
            lambda group, ranked_teams: called_groups.append(group),
        )

        service = FootballDataSyncService(api_key="token-test")
        raw_matches = self._group_stage_payload_matches(main_status="FINISHED")
        raw_matches[-1]["status"] = "IN_PLAY"
        monkeypatch.setattr(
            service,
            "_fetch_matches_payload",
            lambda season=None, status=None: {"matches": raw_matches},
        )
        monkeypatch.setattr(
            service,
            "_fetch_standings_payload",
            lambda season=None: {
                "standings": [
                    {
                        "type": "TOTAL",
                        "group": "GROUP_A",
                        "table": [
                            {
                                "team": {"tla": "ARG", "name": "Argentina"},
                                "playedGames": 3,
                            },
                            {
                                "team": {"tla": "BRA", "name": "Brasil"},
                                "playedGames": 3,
                            },
                        ],
                    }
                ]
            },
        )

        summary = service.sync_matches()

        match.refresh_from_db()
        assert summary.group_recalculations == 0
        assert summary.group_recalculations_source == "api"
        assert called_groups == []

    def test_dry_run_no_escribe_ni_recalcula(
        self, monkeypatch, team_argentina, team_brasil
    ):
        match = Match.objects.create(
            home_team=team_argentina,
            away_team=team_brasil,
            phase=Match.Phase.GROUP,
            group="A",
            scheduled_at=datetime(2026, 6, 12, 13, 0, tzinfo=UTC),
            is_finished=False,
        )

        monkeypatch.setattr(
            "apps.tournament.services.football_data_sync.process_match_result",
            lambda arg_match: [],
        )
        service = FootballDataSyncService(api_key="token-test", use_api_standings=False)
        monkeypatch.setattr(
            service,
            "_fetch_matches_payload",
            lambda season=None, status=None: {
                "matches": [
                    {
                        "utcDate": "2026-06-12T13:00:00Z",
                        "stage": "GROUP_STAGE",
                        "status": "FINISHED",
                        "group": "GROUP_A",
                        "homeTeam": {"tla": "ARG"},
                        "awayTeam": {"tla": "BRA"},
                        "score": {
                            "winner": "HOME_TEAM",
                            "duration": "REGULAR",
                            "fullTime": {"home": 1, "away": 0},
                        },
                    }
                ]
            },
        )

        summary = service.sync_matches(dry_run=True)

        match.refresh_from_db()
        assert summary.updated == 1
        assert summary.scored_matches == 0
        assert summary.group_recalculations == 0
        assert match.is_finished is False
        assert match.home_score is None
        assert match.away_score is None

    def test_knockout_asigna_equipos_desde_api(
        self, monkeypatch, team_argentina, team_brasil
    ):
        match = Match.objects.create(
            phase=Match.Phase.ROUND_OF_32,
            match_label="Cruce pendiente",
            scheduled_at=datetime(2026, 6, 28, 17, 0, tzinfo=UTC),
            is_finished=False,
        )

        monkeypatch.setattr(
            "apps.tournament.services.football_data_sync.process_match_result",
            lambda arg_match: [],
        )

        service = FootballDataSyncService(api_key="token-test", use_api_standings=False)
        monkeypatch.setattr(
            service,
            "_fetch_matches_payload",
            lambda season=None, status=None: {
                "matches": [
                    {
                        "utcDate": "2026-06-28T17:00:00Z",
                        "stage": "LAST_32",
                        "status": "SCHEDULED",
                        "group": None,
                        "homeTeam": {"tla": "ARG"},
                        "awayTeam": {"tla": "BRA"},
                        "score": {
                            "winner": None,
                            "duration": "REGULAR",
                            "fullTime": {"home": None, "away": None},
                        },
                    }
                ]
            },
        )

        summary = service.sync_matches()

        match.refresh_from_db()
        assert summary.updated == 1
        assert match.home_team == team_argentina
        assert match.away_team == team_brasil

    def test_crea_partido_eliminatoria_faltante(
        self, monkeypatch, team_argentina, team_brasil
    ):
        monkeypatch.setattr(
            "apps.tournament.services.football_data_sync.process_match_result",
            lambda arg_match: [],
        )

        service = FootballDataSyncService(
            api_key="token-test",
            use_api_standings=False,
            auto_create_knockout_matches=True,
        )
        monkeypatch.setattr(
            service,
            "_fetch_matches_payload",
            lambda season=None, status=None: {
                "matches": [
                    {
                        "utcDate": "2026-07-01T20:00:00Z",
                        "stage": "QUARTER_FINALS",
                        "status": "SCHEDULED",
                        "group": None,
                        "homeTeam": {"tla": "ARG"},
                        "awayTeam": {"tla": "BRA"},
                        "venue": "Stadium API",
                        "score": {
                            "winner": None,
                            "duration": "REGULAR",
                            "fullTime": {"home": None, "away": None},
                        },
                    }
                ]
            },
        )

        summary = service.sync_matches()

        created = Match.objects.get(
            phase=Match.Phase.QUARTER_FINAL,
            scheduled_at=datetime(2026, 7, 1, 20, 0, tzinfo=UTC),
        )
        assert summary.created == 1
        assert summary.updated == 0
        assert created.home_team == team_argentina
        assert created.away_team == team_brasil
        assert created.venue == "Stadium API"

    def test_no_actualiza_partido_local_ya_finalizado(
        self, monkeypatch, team_argentina, team_brasil
    ):
        match = Match.objects.create(
            home_team=team_argentina,
            away_team=team_brasil,
            phase=Match.Phase.GROUP,
            group="A",
            scheduled_at=datetime(2026, 6, 11, 16, 0, tzinfo=UTC),
            home_score=2,
            away_score=1,
            is_finished=True,
        )

        monkeypatch.setattr(
            "apps.tournament.services.football_data_sync.process_match_result",
            lambda arg_match: (_ for _ in ()).throw(
                AssertionError(
                    "No debería recalcular puntos para partidos ya finalizados"
                )
            ),
        )

        service = FootballDataSyncService(api_key="token-test", use_api_standings=False)
        monkeypatch.setattr(
            service,
            "_fetch_matches_payload",
            lambda season=None, status=None: {
                "matches": [
                    {
                        "utcDate": "2026-06-11T16:00:00Z",
                        "stage": "GROUP_STAGE",
                        "status": "FINISHED",
                        "group": "GROUP_A",
                        "homeTeam": {"tla": "ARG"},
                        "awayTeam": {"tla": "BRA"},
                        "score": {
                            "winner": "AWAY_TEAM",
                            "duration": "REGULAR",
                            "fullTime": {"home": 0, "away": 3},
                        },
                    }
                ]
            },
        )

        summary = service.sync_matches()

        match.refresh_from_db()
        assert summary.updated == 0
        assert summary.unchanged == 1
        assert match.home_score == 2
        assert match.away_score == 1
        assert match.is_finished is True

    def test_no_crea_partido_nuevo_si_api_ya_esta_finished(
        self, monkeypatch, team_argentina, team_brasil
    ):
        monkeypatch.setattr(
            "apps.tournament.services.football_data_sync.process_match_result",
            lambda arg_match: [],
        )

        service = FootballDataSyncService(
            api_key="token-test",
            use_api_standings=False,
            auto_create_knockout_matches=True,
        )
        monkeypatch.setattr(
            service,
            "_fetch_matches_payload",
            lambda season=None, status=None: {
                "matches": [
                    {
                        "utcDate": "2026-07-01T20:00:00Z",
                        "stage": "QUARTER_FINALS",
                        "status": "FINISHED",
                        "group": None,
                        "homeTeam": {"tla": "ARG"},
                        "awayTeam": {"tla": "BRA"},
                        "venue": "Stadium API",
                        "score": {
                            "winner": "HOME_TEAM",
                            "duration": "REGULAR",
                            "fullTime": {"home": 1, "away": 0},
                        },
                    }
                ]
            },
        )

        summary = service.sync_matches()

        assert summary.created == 0
        assert summary.skipped_no_local_match == 1
        assert not Match.objects.filter(
            phase=Match.Phase.QUARTER_FINAL,
            scheduled_at=datetime(2026, 7, 1, 20, 0, tzinfo=UTC),
        ).exists()
