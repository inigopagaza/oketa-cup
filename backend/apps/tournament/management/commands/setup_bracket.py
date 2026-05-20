"""
Management command para configurar el bracket del Mundial 2026.

Lee data/fixtures.json para identificar cada partido por su posición en el
array (scheduled_at es único por partido) y configura los campos next_match
y next_match_slot según el bracket real del torneo.

El comando corrige las inconsistencias en los match_labels del fichero de
fixtures (hay tres referencias que apuntan a la fase incorrecta).
"""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from apps.tournament.models import Match

# Mapping correcto del bracket: índice_origen → (índice_destino, slot)
#
# Los índices son posiciones en el array de data/fixtures.json (base 0).
# Se corrigen tres errores del fichero original:
#   - R16[94] etiqueta G(P88) en vez de G(P72)
#   - QF[99] etiqueta G(P96) en vez de G(P88)
#   - SF[101] etiqueta G(P100) en vez de G(P96)
BRACKET_MAP: dict[int, tuple[int, str]] = {
    # R32 → R16
    72: (94, "away"),
    73: (89, "home"),
    74: (88, "home"),
    75: (89, "away"),
    76: (90, "home"),
    77: (88, "away"),
    78: (90, "away"),
    79: (91, "home"),
    80: (91, "away"),
    81: (93, "home"),
    82: (93, "away"),
    83: (92, "home"),
    84: (92, "away"),
    85: (95, "home"),
    86: (94, "home"),
    87: (95, "away"),
    # R16 → QF
    88: (99, "away"),
    89: (96, "home"),
    90: (96, "away"),
    91: (98, "home"),
    92: (98, "away"),
    93: (97, "home"),
    94: (97, "away"),
    95: (99, "home"),
    # QF → SF
    96: (101, "away"),
    97: (100, "home"),
    98: (100, "away"),
    99: (101, "home"),
}


class Command(BaseCommand):
    help = "Configura next_match / next_match_slot para el bracket del Mundial 2026"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostrar cambios sin aplicarlos",
        )

    def handle(self, *args, **options):
        fixtures_path = Path(settings.BASE_DIR).parent / "data" / "fixtures.json"
        if not fixtures_path.exists():
            raise CommandError(f"No se encontró el fichero: {fixtures_path}")

        with fixtures_path.open(encoding="utf-8") as fh:
            data = json.load(fh)

        dry_run: bool = options["dry_run"]

        # Construir mapping: índice array → Match en BD
        idx_to_match: dict[int, Match] = {}
        skipped = 0
        for idx, entry in enumerate(data):
            scheduled_at = parse_datetime(entry["scheduled_at"])
            phase = entry["phase"]
            try:
                match = Match.objects.get(scheduled_at=scheduled_at, phase=phase)
                idx_to_match[idx] = match
            except Match.DoesNotExist:
                skipped += 1

        if skipped:
            self.stdout.write(
                self.style.WARNING(
                    f"No se encontraron {skipped} partidos en BD (quizá no estén cargados)."
                )
            )

        # Resetear todos los next_match de partidos eliminatorios
        if not dry_run:
            Match.objects.filter(
                phase__in=[
                    Match.Phase.ROUND_OF_32,
                    Match.Phase.ROUND_OF_16,
                    Match.Phase.QUARTER_FINAL,
                    Match.Phase.SEMI_FINAL,
                ]
            ).update(next_match=None, next_match_slot=None)

        updated = 0
        for src_idx, (dst_idx, slot) in BRACKET_MAP.items():
            src = idx_to_match.get(src_idx)
            dst = idx_to_match.get(dst_idx)
            if src is None or dst is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"  ⚠ Partido no encontrado: índice {src_idx} → {dst_idx}"
                    )
                )
                continue
            if dry_run:
                self.stdout.write(
                    f"  [dry-run] [{src.phase}] {src.match_label or src} "
                    f"→ [{dst.phase}] {dst.match_label or dst} ({slot})"
                )
            else:
                src.next_match = dst
                src.next_match_slot = slot
                src.save(update_fields=["next_match", "next_match_slot"])
            updated += 1

        # SF → Final
        try:
            final = Match.objects.get(phase=Match.Phase.FINAL)
        except Match.DoesNotExist:
            self.stdout.write(
                self.style.WARNING("No se encontró el partido de la Final en BD.")
            )
            final = None

        if final is not None:
            for sf_idx, slot in [(100, "home"), (101, "away")]:
                sf = idx_to_match.get(sf_idx)
                if sf is None:
                    continue
                if dry_run:
                    self.stdout.write(
                        f"  [dry-run] [SF] {sf.match_label or sf} → [FIN] Final ({slot})"
                    )
                else:
                    sf.next_match = final
                    sf.next_match_slot = slot
                    sf.save(update_fields=["next_match", "next_match_slot"])
                updated += 1

        verb = "Se procesarían" if dry_run else "Se actualizaron"
        self.stdout.write(
            self.style.SUCCESS(f"✓ {verb} {updated} relaciones del bracket.")
        )
