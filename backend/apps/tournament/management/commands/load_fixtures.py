"""Management command para cargar los partidos del Mundial desde data/fixtures.json."""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.tournament.models import Match, NationalTeam


class Command(BaseCommand):
    help = "Carga todos los partidos del Mundial desde data/fixtures.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Eliminar todos los partidos existentes antes de cargar",
        )
        parser.add_argument(
            "--skip-knockout",
            action="store_true",
            help="No cargar los partidos de fase eliminatoria (sólo grupos)",
        )

    def handle(self, *args, **options):
        fixtures_path = Path(settings.BASE_DIR) / "data" / "fixtures.json"

        # Compatibilidad con estructura antigua (raíz del repo).
        if not fixtures_path.exists():
            legacy_path = Path(__file__).resolve().parents[5] / "data" / "fixtures.json"
            if legacy_path.exists():
                fixtures_path = legacy_path

        if not fixtures_path.exists():
            raise CommandError(f"No se encontró el fichero: {fixtures_path}")

        with open(fixtures_path, encoding="utf-8") as f:
            fixtures = json.load(f)

        if options["clear"]:
            deleted, _ = Match.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f"Eliminados {deleted} partidos existentes.")
            )

        group_phase = Match.Phase.GROUP
        created = skipped = errors = 0

        for entry in fixtures:
            phase = entry["phase"]
            is_group = phase == group_phase

            if options["skip_knockout"] and not is_group:
                continue

            home_team = away_team = None

            if is_group:
                home_code = entry.get("home")
                away_code = entry.get("away")
                try:
                    home_team = NationalTeam.objects.get(code=home_code)
                    away_team = NationalTeam.objects.get(code=away_code)
                except NationalTeam.DoesNotExist as exc:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Equipo no encontrado: {exc} — entrada omitida"
                        )
                    )
                    errors += 1
                    continue

            match, was_created = Match.objects.get_or_create(
                scheduled_at=entry["scheduled_at"],
                phase=phase,
                group=entry.get("group", ""),
                home_team=home_team,
                away_team=away_team,
                defaults={
                    "match_label": entry.get("match_label", ""),
                    "venue": entry.get("venue", ""),
                },
            )

            if was_created:
                created += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Carga completada: {created} creados, {skipped} ya existían, {errors} errores."
            )
        )
