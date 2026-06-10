"""Sincroniza resultados de football-data.org con los partidos locales."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.tournament.services.football_data_sync import (
    FootballDataSyncError,
    FootballDataSyncService,
)


class Command(BaseCommand):
    help = "Sincroniza resultados del Mundial desde football-data.org"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Calcula cambios sin escribir en base de datos",
        )
        parser.add_argument(
            "--season",
            type=int,
            default=None,
            help="Filtrar por temporada (año inicial, p.ej. 2026)",
        )
        parser.add_argument(
            "--status",
            type=str,
            default=None,
            help="Filtrar por estado de partido (SCHEDULED, FINISHED, ...)",
        )

    def handle(self, *args, **options):
        api_key = getattr(settings, "FOOTBALL_DATA_API_KEY", "")
        if not api_key:
            raise CommandError(
                "FOOTBALL_DATA_API_KEY no está configurada. "
                "Define la variable en backend/.env (local) o variables de entorno (producción)."
            )

        service = FootballDataSyncService(
            api_key=api_key,
            competition_code=getattr(settings, "FOOTBALL_DATA_COMPETITION_CODE", "WC"),
            base_url=getattr(
                settings,
                "FOOTBALL_DATA_BASE_URL",
                "https://api.football-data.org/v4",
            ),
            timeout_seconds=getattr(settings, "FOOTBALL_DATA_TIMEOUT_SECONDS", 20),
            use_api_standings=getattr(
                settings,
                "FOOTBALL_DATA_USE_API_STANDINGS",
                True,
            ),
            auto_create_knockout_matches=getattr(
                settings,
                "FOOTBALL_DATA_AUTO_CREATE_KNOCKOUT",
                True,
            ),
        )

        try:
            summary = service.sync_matches(
                dry_run=options["dry_run"],
                season=options["season"],
                status=options["status"],
            )
        except FootballDataSyncError as exc:
            raise CommandError(str(exc)) from exc

        mode = "DRY-RUN" if options["dry_run"] else "APLICADO"
        self.stdout.write(self.style.SUCCESS(f"Sincronización {mode} completada."))
        self.stdout.write(f"- Partidos API leídos: {summary.fetched}")
        self.stdout.write(f"- Partidos locales encontrados: {summary.matched}")
        self.stdout.write(f"- Partidos creados automáticamente: {summary.created}")
        self.stdout.write(f"- Partidos actualizados: {summary.updated}")
        self.stdout.write(f"- Partidos sin cambios: {summary.unchanged}")
        self.stdout.write(f"- Puntuaciones recalculadas: {summary.scored_matches}")
        self.stdout.write(
            f"- Grupos recalculados: {summary.group_recalculations} "
            f"(fuente={summary.group_recalculations_source})"
        )
        self.stdout.write(
            f"- Saltados por stage no mapeado: {summary.skipped_unmapped_stage}"
        )
        self.stdout.write(f"- Saltados por match ambiguo: {summary.skipped_ambiguous}")
        self.stdout.write(
            f"- Saltados sin match local: {summary.skipped_no_local_match}"
        )
