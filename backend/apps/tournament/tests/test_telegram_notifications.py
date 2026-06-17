from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from apps.tournament.management.commands.run_telegram_notifier import (
    Command as RunNotifierCommand,
)
from apps.tournament.management.commands.send_daily_telegram_summary import (
    Command as SendSummaryCommand,
)
from apps.tournament.models import Match
from apps.tournament.services.daily_telegram_summary import build_daily_summary
from apps.tournament.services.telegram_client import (
    TelegramConfigError,
    send_telegram_message,
)


@pytest.mark.django_db
class TestDailyTelegramSummary:
    def test_build_daily_summary_without_matches(self):
        text = build_daily_summary(date(2026, 6, 11))
        assert "Hoy no hay partidos." in text

    def test_build_daily_summary_includes_flags_pending_and_finished(
        self,
        team_argentina,
        team_brasil,
    ):
        Match.objects.create(
            home_team=team_argentina,
            away_team=team_brasil,
            phase=Match.Phase.GROUP,
            group="A",
            scheduled_at=datetime(2026, 6, 11, 16, 0, tzinfo=UTC),
            is_finished=False,
        )
        Match.objects.create(
            home_team=team_brasil,
            away_team=team_argentina,
            phase=Match.Phase.GROUP,
            group="A",
            scheduled_at=datetime(2026, 6, 11, 20, 0, tzinfo=UTC),
            home_score=1,
            away_score=2,
            is_finished=True,
        )

        text = build_daily_summary(date(2026, 6, 11))

        assert "Partidos de hoy:" in text
        assert "Resultados ya cargados:" in text
        assert "11/06/2026" in text
        assert "🇦🇷 ARG" in text
        assert "🇧🇷 BRA" in text


class TestTelegramClient:
    def test_send_telegram_message_requires_token_and_chat(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

        with pytest.raises(TelegramConfigError):
            send_telegram_message("hola")

    def test_send_telegram_message_dry_run(self, monkeypatch, capsys):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "-1001")
        monkeypatch.setenv("TELEGRAM_DRY_RUN", "true")

        send_telegram_message("mensaje-test")

        out = capsys.readouterr().out
        assert "[DRY_RUN]" in out
        assert "mensaje-test" in out

    def test_send_telegram_message_calls_api(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "-1001")
        monkeypatch.setenv("TELEGRAM_DRY_RUN", "false")

        payload_seen: dict[str, str] = {}

        class DummyResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"ok": True}

        class DummyClient:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def post(self, url, json):
                payload_seen["url"] = url
                payload_seen["chat_id"] = json["chat_id"]
                payload_seen["text"] = json["text"]
                return DummyResponse()

        monkeypatch.setattr(
            "apps.tournament.services.telegram_client.httpx.Client",
            lambda timeout: DummyClient(),
        )

        send_telegram_message("mensaje-test")

        assert payload_seen["chat_id"] == "-1001"
        assert payload_seen["text"] == "mensaje-test"
        assert payload_seen["url"].endswith("/sendMessage")

    def test_send_telegram_message_raises_runtime_on_telegram_error(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "-1001")
        monkeypatch.setenv("TELEGRAM_DRY_RUN", "false")

        class DummyResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"ok": False, "description": "bad"}

        class DummyClient:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def post(self, url, json):
                return DummyResponse()

        monkeypatch.setattr(
            "apps.tournament.services.telegram_client.httpx.Client",
            lambda timeout: DummyClient(),
        )

        with pytest.raises(RuntimeError):
            send_telegram_message("mensaje-test")


class TestTelegramCommands:
    def test_send_daily_telegram_summary_command_uses_date_arg(
        self, monkeypatch, capsys
    ):
        monkeypatch.setattr(
            "apps.tournament.management.commands.send_daily_telegram_summary.build_daily_summary",
            lambda day: f"resumen {day.isoformat()}",
        )
        sent: list[str] = []
        monkeypatch.setattr(
            "apps.tournament.management.commands.send_daily_telegram_summary.send_telegram_message",
            lambda text: sent.append(text),
        )

        cmd = SendSummaryCommand()
        cmd.handle(date="2026-06-12")

        out = capsys.readouterr().out
        assert "Construyendo resumen para 2026-06-12" in out
        assert sent == ["resumen 2026-06-12"]

    def test_run_telegram_notifier_command_disabled(self, monkeypatch, capsys):
        monkeypatch.setenv("TELEGRAM_ENABLED", "false")

        cmd = RunNotifierCommand()
        cmd.handle()

        out = capsys.readouterr().out
        assert "TELEGRAM_ENABLED=false. Saliendo." in out
