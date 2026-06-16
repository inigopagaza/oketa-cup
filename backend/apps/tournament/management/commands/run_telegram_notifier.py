from __future__ import annotations

import os
import signal
import sys
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from django.core.management.base import BaseCommand

from apps.tournament.services.daily_telegram_summary import build_daily_summary
from apps.tournament.services.telegram_client import send_telegram_message


class Command(BaseCommand):
    help = "Lanza scheduler diario para Telegram a las 10:00 Europe/Madrid"

    def handle(self, *args, **options):
        tz = ZoneInfo(os.environ.get("TZ", "Europe/Madrid"))
        enabled = os.environ.get("TELEGRAM_ENABLED", "true").lower() == "true"
        start_date = date.fromisoformat(
            os.environ.get("TELEGRAM_START_DATE", "2026-06-11")
        )
        end_date = date.fromisoformat(os.environ.get("TELEGRAM_END_DATE", "2026-07-20"))

        if not enabled:
            self.stdout.write("TELEGRAM_ENABLED=false. Saliendo.")
            return

        # Idempotencia en memoria (se reinicia si el contenedor cae).
        # Para persistencia total usar modelo DailyNotificationLog en BD.
        sent_dates: set[str] = set()

        def job() -> None:
            now = datetime.now(tz)
            today = now.date()

            if today < start_date:
                print(f"Aún no inicia ventana de envíos ({start_date.isoformat()}).")
                return

            if today > end_date:
                print(
                    f"Ventana de envíos cerrada desde {end_date.isoformat()}. Saliendo."
                )
                scheduler.shutdown(wait=False)
                sys.exit(0)

            if today.isoformat() in sent_dates:
                print(f"Resumen ya enviado hoy: {today.isoformat()}")
                return

            try:
                text = build_daily_summary(today)
                send_telegram_message(text)
                sent_dates.add(today.isoformat())
                print(f"Resumen enviado para {today.isoformat()}")
            except Exception as exc:  # noqa: BLE001
                print(f"ERROR enviando resumen: {exc}")

        scheduler = BackgroundScheduler(timezone=tz)
        scheduler.add_job(
            job,
            trigger="cron",
            hour=10,
            minute=0,
            id="telegram_daily_summary",
        )
        scheduler.start()

        self.stdout.write("Notifier Telegram iniciado. Esperando ejecuciones...")

        def _shutdown(*_):
            scheduler.shutdown(wait=False)
            sys.exit(0)

        signal.signal(signal.SIGTERM, _shutdown)
        signal.signal(signal.SIGINT, _shutdown)

        while True:
            time.sleep(5)
