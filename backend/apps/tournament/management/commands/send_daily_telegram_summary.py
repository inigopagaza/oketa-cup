from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand

from apps.tournament.services.daily_telegram_summary import build_daily_summary
from apps.tournament.services.telegram_client import send_telegram_message


class Command(BaseCommand):
    help = "Envia el resumen diario del Mundial a Telegram"

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            default="",
            help="Fecha en formato YYYY-MM-DD (por defecto: hoy)",
        )

    def handle(self, *args, **options):
        day = date.fromisoformat(options["date"]) if options["date"] else date.today()
        self.stdout.write(f"Construyendo resumen para {day}...")
        text = build_daily_summary(day)
        self.stdout.write(text)
        self.stdout.write("---")
        send_telegram_message(text)
        self.stdout.write(self.style.SUCCESS("Resumen enviado correctamente"))
