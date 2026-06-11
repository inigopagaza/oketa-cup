from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.pool.models import REASON_GROUP_ADVANCE, REASON_GROUP_FIRST, ScoreLog


class Command(BaseCommand):
    help = "Elimina los ScoreLog de clasificación de grupo generados por error"

    def add_arguments(self, parser):
        parser.add_argument(
            "--group",
            type=str,
            default=None,
            help="Filtra por letra de grupo (A-L). Si no se indica, limpia todos.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra cuántos registros se borrarían sin eliminar nada",
        )

    def handle(self, *args, **options):
        group = options["group"]
        dry_run = options["dry_run"]

        queryset = ScoreLog.objects.filter(
            reason_code__in=[REASON_GROUP_ADVANCE, REASON_GROUP_FIRST],
        )
        if group:
            group = group.upper().strip()
            queryset = queryset.filter(reason_context__group=group)

        count = queryset.count()
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Se borrarían {count} ScoreLog de clasificación de grupo."
                )
            )
            return

        deleted, _ = queryset.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Borrados {deleted} ScoreLog de clasificación de grupo."
            )
        )
