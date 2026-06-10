"""Sincronización de resultados desde football-data.org."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.db.models import QuerySet
from django.utils import timezone

from apps.pool.services.scoring import (
    process_group_completion,
    process_group_completion_from_standings,
    process_match_result,
)
from apps.tournament.models import Match, NationalTeam

logger = logging.getLogger(__name__)


@dataclass
class SyncSummary:
    """Resumen del resultado de una ejecución de sincronización."""

    fetched: int = 0
    matched: int = 0
    updated: int = 0
    unchanged: int = 0
    scored_matches: int = 0
    created: int = 0
    group_recalculations: int = 0
    group_recalculations_source: str = "none"
    skipped_unmapped_stage: int = 0
    skipped_ambiguous: int = 0
    skipped_no_local_match: int = 0


class FootballDataSyncError(Exception):
    """Error funcional al sincronizar con football-data.org."""


class FootballDataSyncService:
    """Cliente/servicio para importar resultados desde football-data.org."""

    _STAGE_TO_PHASE: dict[str, str] = {
        "GROUP_STAGE": Match.Phase.GROUP,
        "LAST_32": Match.Phase.ROUND_OF_32,
        "LAST_16": Match.Phase.ROUND_OF_16,
        "QUARTER_FINALS": Match.Phase.QUARTER_FINAL,
        "SEMI_FINALS": Match.Phase.SEMI_FINAL,
        "THIRD_PLACE": Match.Phase.THIRD_PLACE,
        "FINAL": Match.Phase.FINAL,
    }

    def __init__(
        self,
        api_key: str,
        competition_code: str = "WC",
        base_url: str = "https://api.football-data.org/v4",
        timeout_seconds: int = 20,
        use_api_standings: bool = True,
        auto_create_knockout_matches: bool = True,
    ) -> None:
        if not api_key:
            raise FootballDataSyncError(
                "FOOTBALL_DATA_API_KEY no está configurada en entorno."
            )

        self.api_key = api_key
        self.competition_code = competition_code
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.use_api_standings = use_api_standings
        self.auto_create_knockout_matches = auto_create_knockout_matches
        self._team_by_code: dict[str, NationalTeam] = {}

    def sync_matches(
        self,
        *,
        dry_run: bool = False,
        season: int | None = None,
        status: str | None = None,
    ) -> SyncSummary:
        """Sincroniza partidos de la competición configurada contra la BD local."""
        response = self._fetch_matches_payload(season=season, status=status)
        raw_matches = response.get("matches", [])

        summary = SyncSummary(fetched=len(raw_matches))
        groups_to_recalculate: set[str] = set()

        for raw_match in raw_matches:
            phase = self._map_stage_to_phase(raw_match.get("stage"))
            if phase is None:
                summary.skipped_unmapped_stage += 1
                continue

            local_match = self._find_local_match(raw_match, phase)
            if local_match is None:
                if not dry_run and self.auto_create_knockout_matches:
                    created_match = self._create_missing_match(
                        raw_match=raw_match, phase=phase
                    )
                    if created_match is not None:
                        local_match = created_match
                        summary.created += 1
                if local_match is None:
                    summary.skipped_no_local_match += 1
                    continue

            if isinstance(local_match, list):
                summary.skipped_ambiguous += 1
                continue

            summary.matched += 1

            changed, became_finished = self._apply_match_update(
                local_match,
                raw_match,
                phase=phase,
                dry_run=dry_run,
            )

            if not changed:
                summary.unchanged += 1
                continue

            summary.updated += 1

            if became_finished and not dry_run:
                process_match_result(local_match)
                summary.scored_matches += 1
                if local_match.phase == Match.Phase.GROUP and local_match.group:
                    groups_to_recalculate.add(local_match.group)

        if not dry_run:
            if self.use_api_standings:
                try:
                    summary.group_recalculations = self._recalculate_groups_from_api(
                        season=season
                    )
                    summary.group_recalculations_source = "api"
                except FootballDataSyncError as exc:
                    logger.warning(
                        "No se pudieron aplicar standings API (%s). Fallback a cálculo local.",
                        exc,
                    )
                    for group in sorted(groups_to_recalculate):
                        process_group_completion(group)
                        summary.group_recalculations += 1
                    summary.group_recalculations_source = "local"
            else:
                for group in sorted(groups_to_recalculate):
                    process_group_completion(group)
                    summary.group_recalculations += 1
                summary.group_recalculations_source = "local"

        return summary

    def _fetch_matches_payload(
        self, *, season: int | None = None, status: str | None = None
    ) -> dict:
        params: dict[str, str] = {}
        if season is not None:
            params["season"] = str(season)
        if status:
            params["status"] = status

        endpoint = f"/competitions/{self.competition_code}/matches"
        url = f"{self.base_url}{endpoint}"
        if params:
            url = f"{url}?{urlencode(params)}"

        req = Request(
            url,
            headers={
                "X-Auth-Token": self.api_key,
                "Accept": "application/json",
            },
        )

        try:
            with urlopen(req, timeout=self.timeout_seconds) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            raise FootballDataSyncError(
                f"Error HTTP {exc.code} al consultar football-data.org"
            ) from exc
        except URLError as exc:
            raise FootballDataSyncError(
                f"No se pudo conectar con football-data.org: {exc.reason}"
            ) from exc

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise FootballDataSyncError(
                "Respuesta JSON inválida de football-data.org"
            ) from exc

        if "matches" not in data:
            raise FootballDataSyncError("La respuesta no contiene el nodo 'matches'.")

        return data

    def _fetch_standings_payload(self, *, season: int | None = None) -> dict:
        params: dict[str, str] = {}
        if season is not None:
            params["season"] = str(season)

        endpoint = f"/competitions/{self.competition_code}/standings"
        url = f"{self.base_url}{endpoint}"
        if params:
            url = f"{url}?{urlencode(params)}"

        req = Request(
            url,
            headers={
                "X-Auth-Token": self.api_key,
                "Accept": "application/json",
            },
        )

        try:
            with urlopen(req, timeout=self.timeout_seconds) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            raise FootballDataSyncError(
                f"Error HTTP {exc.code} al consultar standings en football-data.org"
            ) from exc
        except URLError as exc:
            raise FootballDataSyncError(
                f"No se pudo conectar con football-data.org (standings): {exc.reason}"
            ) from exc

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise FootballDataSyncError(
                "Respuesta JSON inválida en standings de football-data.org"
            ) from exc

        if "standings" not in data:
            raise FootballDataSyncError(
                "La respuesta de standings no contiene el nodo 'standings'."
            )
        return data

    def _map_stage_to_phase(self, stage: str | None) -> str | None:
        if not stage:
            return None
        return self._STAGE_TO_PHASE.get(stage)

    def _find_local_match(
        self, raw_match: dict, phase: str
    ) -> Match | list[Match] | None:
        scheduled_at = self._parse_api_datetime(raw_match.get("utcDate"))
        if scheduled_at is None:
            return None

        group_letter = self._extract_group_letter(raw_match.get("group"))
        home = self._resolve_local_team(raw_match.get("homeTeam", {}).get("tla"))
        away = self._resolve_local_team(raw_match.get("awayTeam", {}).get("tla"))

        exact_base_qs = Match.objects.filter(phase=phase, scheduled_at=scheduled_at)
        exact_qs = exact_base_qs
        if phase == Match.Phase.GROUP and group_letter:
            exact_qs = exact_qs.filter(group=group_letter)
        exact_qs = self._filter_by_known_teams(exact_qs, home=home, away=away)
        if exact_qs.count() == 1:
            return exact_qs.first()
        if exact_qs.count() > 1:
            return list(exact_qs)

        # Fallback 1: aceptar placeholders sin equipos aún asignados.
        if home is not None or away is not None:
            exact_placeholder_qs = exact_base_qs
            if phase == Match.Phase.GROUP and group_letter:
                exact_placeholder_qs = exact_placeholder_qs.filter(group=group_letter)
            if exact_placeholder_qs.count() == 1:
                return exact_placeholder_qs.first()
            if exact_placeholder_qs.count() > 1:
                return list(exact_placeholder_qs)

        # Fallback tolerante por posibles desfases de zona horaria/segundos.
        start = scheduled_at - timedelta(hours=3)
        end = scheduled_at + timedelta(hours=3)
        candidate_base_qs = Match.objects.filter(
            phase=phase,
            scheduled_at__gte=start,
            scheduled_at__lte=end,
        )
        candidate_qs = candidate_base_qs
        if phase == Match.Phase.GROUP and group_letter:
            candidate_qs = candidate_qs.filter(group=group_letter)

        candidate_qs = self._filter_by_known_teams(candidate_qs, home=home, away=away)
        candidates = list(candidate_qs)
        if not candidates:
            # Fallback 2: mismo rango horario, sin forzar equipos, para placeholders.
            if home is not None or away is not None:
                candidate_qs = candidate_base_qs
                if phase == Match.Phase.GROUP and group_letter:
                    candidate_qs = candidate_qs.filter(group=group_letter)
                candidates = list(candidate_qs)
                if not candidates:
                    return None
            else:
                return None
        if len(candidates) == 1:
            return candidates[0]

        # Si hay varios candidatos, intentamos escoger por menor distancia horaria.
        candidates.sort(
            key=lambda m: abs((m.scheduled_at - scheduled_at).total_seconds())
        )
        best = candidates[0]
        best_delta = abs((best.scheduled_at - scheduled_at).total_seconds())
        second_delta = abs((candidates[1].scheduled_at - scheduled_at).total_seconds())
        if best_delta == second_delta:
            return candidates
        return best

    def _filter_by_known_teams(
        self,
        qs: QuerySet[Match],
        *,
        home: NationalTeam | None,
        away: NationalTeam | None,
    ) -> QuerySet[Match]:
        if home is not None:
            qs = qs.filter(home_team=home)
        if away is not None:
            qs = qs.filter(away_team=away)
        return qs

    def _apply_match_update(
        self,
        match: Match,
        raw_match: dict,
        *,
        phase: str,
        dry_run: bool,
    ) -> tuple[bool, bool]:
        status = (raw_match.get("status") or "").upper()
        is_finished = status == "FINISHED"

        if match.is_finished and not is_finished:
            # Evitamos retroceder estados finales en caso de inconsistencia externa.
            return False, False

        score_data = raw_match.get("score") or {}
        full_time = score_data.get("fullTime") or {}

        desired_home_score = self._as_int_or_none(full_time.get("home"))
        desired_away_score = self._as_int_or_none(full_time.get("away"))

        duration = (score_data.get("duration") or "").upper()
        winner = (score_data.get("winner") or "").upper()
        desired_home_team = self._resolve_local_team(
            raw_match.get("homeTeam", {}).get("tla")
        )
        desired_away_team = self._resolve_local_team(
            raw_match.get("awayTeam", {}).get("tla")
        )

        if phase == Match.Phase.GROUP:
            desired_decided_in_90 = True
            desired_penalties_winner = ""
        else:
            desired_decided_in_90 = duration == "REGULAR" if is_finished else True
            desired_penalties_winner = ""
            if duration == "PENALTY_SHOOTOUT" and is_finished:
                if winner == "HOME_TEAM":
                    desired_penalties_winner = Match.PenaltiesWinner.HOME
                elif winner == "AWAY_TEAM":
                    desired_penalties_winner = Match.PenaltiesWinner.AWAY

        changed_fields: list[str] = []

        if desired_home_team is not None and match.home_team_id != desired_home_team.id:
            match.home_team = desired_home_team
            changed_fields.append("home_team")
        if desired_away_team is not None and match.away_team_id != desired_away_team.id:
            match.away_team = desired_away_team
            changed_fields.append("away_team")

        if match.home_score != desired_home_score:
            match.home_score = desired_home_score
            changed_fields.append("home_score")
        if match.away_score != desired_away_score:
            match.away_score = desired_away_score
            changed_fields.append("away_score")
        if match.is_finished != is_finished:
            match.is_finished = is_finished
            changed_fields.append("is_finished")
        if match.decided_in_90 != desired_decided_in_90:
            match.decided_in_90 = desired_decided_in_90
            changed_fields.append("decided_in_90")
        if match.penalties_winner != desired_penalties_winner:
            match.penalties_winner = desired_penalties_winner
            changed_fields.append("penalties_winner")

        if not changed_fields:
            return False, False

        became_finished = is_finished

        if not dry_run:
            match.save(update_fields=changed_fields)

        return True, became_finished

    def _resolve_local_team(self, code: str | None) -> NationalTeam | None:
        if not code:
            return None
        normalized = code.upper()
        if normalized in self._team_by_code:
            return self._team_by_code[normalized]
        team = NationalTeam.objects.filter(code=normalized).first()
        if team is not None:
            self._team_by_code[normalized] = team
        return team

    def _resolve_local_team_from_api_team(self, api_team: dict) -> NationalTeam | None:
        by_code = self._resolve_local_team(api_team.get("tla"))
        if by_code is not None:
            return by_code

        team_name = str(api_team.get("name") or "").strip()
        if not team_name:
            return None
        return NationalTeam.objects.filter(name__iexact=team_name).first()

    def _create_missing_match(self, *, raw_match: dict, phase: str) -> Match | None:
        if phase == Match.Phase.GROUP:
            return None

        scheduled_at = self._parse_api_datetime(raw_match.get("utcDate"))
        if scheduled_at is None:
            return None

        home_team = self._resolve_local_team(raw_match.get("homeTeam", {}).get("tla"))
        away_team = self._resolve_local_team(raw_match.get("awayTeam", {}).get("tla"))
        group_letter = self._extract_group_letter(raw_match.get("group"))
        stage = str(raw_match.get("stage") or "").strip()
        match_label = str(raw_match.get("group") or stage or "Cruce API")
        venue = str(raw_match.get("venue") or "")

        match = Match.objects.create(
            home_team=home_team,
            away_team=away_team,
            phase=phase,
            group=group_letter if phase == Match.Phase.GROUP else "",
            match_label=match_label,
            venue=venue,
            scheduled_at=scheduled_at,
            is_finished=False,
            decided_in_90=True,
            penalties_winner="",
        )
        logger.info(
            "Creado partido faltante desde API: id=%s phase=%s scheduled_at=%s",
            match.id,
            phase,
            scheduled_at,
        )
        return match

    def _recalculate_groups_from_api(self, *, season: int | None = None) -> int:
        payload = self._fetch_standings_payload(season=season)
        standings = payload.get("standings", [])
        recalculated = 0

        for standing in standings:
            standing_type = str(standing.get("type") or "").upper()
            if standing_type != "TOTAL":
                continue

            group_letter = self._extract_group_letter(standing.get("group"))
            if not group_letter:
                continue

            table = standing.get("table") or []
            ranked_teams: list[NationalTeam] = []
            for row in table:
                team_data = row.get("team") or {}
                team = self._resolve_local_team_from_api_team(team_data)
                if team is not None:
                    ranked_teams.append(team)

            if len(ranked_teams) < 2:
                logger.warning(
                    "Grupo %s: standings API sin equipos suficientes mapeados.",
                    group_letter,
                )
                continue

            process_group_completion_from_standings(group_letter, ranked_teams)
            recalculated += 1

        return recalculated

    def _parse_api_datetime(self, raw_value: str | None) -> datetime | None:
        if not raw_value:
            return None
        try:
            parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        except ValueError:
            return None

        if timezone.is_naive(parsed):
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    def _extract_group_letter(self, raw_group: str | None) -> str:
        if not raw_group:
            return ""
        match = re.search(r"([A-L])$", raw_group.upper())
        return match.group(1) if match else ""

    def _as_int_or_none(self, value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(cast(Any, value))
        except (TypeError, ValueError):
            return None
