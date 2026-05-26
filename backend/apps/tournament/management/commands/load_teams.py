"""
Management command: load_teams

Carga las 48 selecciones nacionales desde data/teams.json a la base de datos.
Es idempotente: si un equipo ya existe (por código FIFA), lo actualiza.

Uso:
    python manage.py load_teams
    python manage.py load_teams --file /ruta/alternativa/teams.json
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.tournament.models import NationalTeam


class Command(BaseCommand):
    """Carga las selecciones nacionales desde el fichero JSON."""

    help = "Carga las 48 selecciones del Mundial desde data/teams.json"

    def add_arguments(self, parser) -> None:  # type: ignore[override]
        parser.add_argument(
            "--file",
            type=str,
            default=None,
            help="Ruta alternativa al fichero JSON (por defecto: data/teams.json)",
        )

    def handle(self, *args, **options) -> None:  # type: ignore[override]
        # Resolver la ruta del fichero
        if options["file"]:
            data_path = Path(options["file"])
        else:
            from django.conf import settings

            data_path = Path(settings.BASE_DIR) / "data" / "teams.json"

        if not data_path.exists():
            raise CommandError(f"No se encontró el fichero: {data_path}")

        with data_path.open(encoding="utf-8") as f:
            teams_data = json.load(f)

        created_count = 0
        updated_count = 0

        for team_data in teams_data:
            team, created = NationalTeam.objects.update_or_create(
                code=team_data["code"],
                defaults={
                    "name": team_data["name"],
                    "flag_emoji": team_data.get("flag_emoji", ""),
                    "group": team_data["group"],
                    "price": team_data["price"],
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ {created_count} selecciones creadas, {updated_count} actualizadas."
            )
        )
