from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.db.models import QuerySet

from apps.tournament.models import Match

MADRID_TZ = ZoneInfo("Europe/Madrid")
WEEKDAY_ES = [
    "lunes",
    "martes",
    "miercoles",
    "jueves",
    "viernes",
    "sabado",
    "domingo",
]


def _today_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=MADRID_TZ)
    end = datetime.combine(day, time.max, tzinfo=MADRID_TZ)
    return start, end


def _matches_for_day(day: date) -> QuerySet[Match]:
    start, end = _today_bounds(day)
    return (
        Match.objects.select_related("home_team", "away_team")
        .filter(scheduled_at__range=(start, end))
        .order_by("scheduled_at")
    )


def _weekday_name_es(day: date) -> str:
    return WEEKDAY_ES[day.weekday()]


def build_daily_summary(day: date) -> str:
    matches = list(_matches_for_day(day))

    if not matches:
        return f"Mundial 2026 - {day:%d/%m/%Y}\n\nHoy no hay partidos."

    pending: list[str] = []
    finished: list[str] = []

    for m in matches:
        home_flag = m.home_team.flag_emoji if m.home_team_id and m.home_team else ""
        away_flag = m.away_team.flag_emoji if m.away_team_id and m.away_team else ""
        home = m.home_team.code if m.home_team_id else "TBD"
        away = m.away_team.code if m.away_team_id else "TBD"
        home_label = f"{home_flag} {home}".strip()
        away_label = f"{away_flag} {away}".strip()
        hour = m.scheduled_at.astimezone(MADRID_TZ).strftime("%H:%M")
        phase = m.get_phase_display()

        if m.is_finished and m.home_score is not None and m.away_score is not None:
            finished.append(
                f"- {home_label} {m.home_score}-{m.away_score} {away_label} ({phase})"
            )
        else:
            pending.append(f"- {hour} {home_label} vs {away_label} ({phase})")

    lines = [f"⚽ Mundial 2026 — {_weekday_name_es(day)} {day:%d/%m/%Y}", ""]

    if pending:
        lines.append("📅 Partidos de hoy:")
        lines.extend(pending)
        lines.append("")

    if finished:
        lines.append("✅ Resultados ya cargados:")
        lines.extend(finished)
        lines.append("")

    return "\n".join(lines).strip()
