"""Vistas de la app pool (stub inicial)."""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.tournament.models import Match, NationalTeam, TournamentConfig

from .models import Participant


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """
    Dashboard principal del participante.

    Muestra la clasificación general, los equipos del usuario
    y los partidos del día.
    """
    # El admin no necesita confirmar selección
    if not request.user.is_staff and not request.user.has_confirmed_selection:  # type: ignore[union-attr]
        return redirect("pool:select_teams")

    participant, _ = Participant.objects.get_or_create(user=request.user)

    # Clasificación general: participantes normales ordenados por puntos
    ranking = sorted(
        Participant.objects.select_related("user")
        .prefetch_related("teams")
        .filter(user__is_staff=False)
        .distinct(),
        key=lambda p: p.total_points,
        reverse=True,
    )

    # Partidos de hoy
    from django.utils import timezone

    today = timezone.now().date()
    todays_matches = Match.objects.filter(scheduled_at__date=today).select_related(
        "home_team", "away_team"
    )

    # Puntos por equipo del participante actual
    team_scores = [
        {
            "team": team,
            "points": participant.score_logs.filter(team=team).aggregate(
                total=__import__("django.db.models", fromlist=["Sum"]).Sum(
                    "points_earned"
                )
            )["total"]
            or 0,
        }
        for team in participant.teams.all()
    ]

    # Partidos pendientes de resultado y partidos finalizados (para el panel de admin)
    pending_matches = None
    finished_matches = None
    finished_matches_date = None
    tournament_config = None
    prize_participants = None
    if request.user.is_staff:
        import datetime

        from django.utils import timezone as _tz

        pending_matches = (
            Match.objects.filter(is_finished=False, scheduled_at__lte=_tz.now())
            .select_related("home_team", "away_team")
            .order_by("scheduled_at")
        )
        today = _tz.now().date()
        fecha_str = request.GET.get("fecha", str(today))
        try:
            finished_matches_date = datetime.date.fromisoformat(fecha_str)
        except ValueError:
            finished_matches_date = today
        finished_matches = (
            Match.objects.filter(
                is_finished=True, scheduled_at__date=finished_matches_date
            )
            .select_related("home_team", "away_team")
            .order_by("scheduled_at")
        )

        # Datos para adjudicación de premios individuales
        from apps.tournament.views import (
            _REASON_GOALKEEPER,
            _REASON_MVP,
            _REASON_TOP_SCORER,
        )

        from .models import ScoreLog

        tournament_config = TournamentConfig.get()
        prize_participants = []
        for p in Participant.objects.filter(user__is_staff=False).select_related(
            "user"
        ):  # pyright: ignore[reportAttributeAccessIssue]
            prize_participants.append(
                {
                    "participant": p,
                    "mvp_correct": ScoreLog.objects.filter(
                        participant=p, match=None, reason=_REASON_MVP
                    ).exists(),  # pyright: ignore[reportAttributeAccessIssue]
                    "top_scorer_correct": ScoreLog.objects.filter(
                        participant=p, match=None, reason=_REASON_TOP_SCORER
                    ).exists(),  # pyright: ignore[reportAttributeAccessIssue]
                    "goalkeeper_correct": ScoreLog.objects.filter(
                        participant=p, match=None, reason=_REASON_GOALKEEPER
                    ).exists(),  # pyright: ignore[reportAttributeAccessIssue]
                }
            )

    return render(
        request,
        "pool/dashboard.html",
        {
            "participant": participant,
            "ranking": ranking,
            "todays_matches": todays_matches,
            "team_scores": team_scores,
            "pending_matches": pending_matches,
            "finished_matches": finished_matches,
            "finished_matches_date": finished_matches_date,
            "tournament_config": tournament_config if request.user.is_staff else None,
            "prize_participants": prize_participants if request.user.is_staff else None,
        },
    )


@login_required
def select_teams(request: HttpRequest) -> HttpResponse:
    """
    Página de selección de equipos.

    Solo accesible si el usuario no ha confirmado su selección.
    Muestra todas las selecciones con precio y presupuesto restante.
    """
    if request.user.is_staff or request.user.has_confirmed_selection:  # type: ignore[union-attr]
        return redirect("pool:dashboard")

    config = TournamentConfig.get()
    teams = NationalTeam.objects.all().order_by("group", "name")

    return render(
        request,
        "pool/select_teams.html",
        {
            "teams": teams,
            "budget": config.budget,
        },
    )


@login_required
@require_POST
def confirm_selection(request: HttpRequest) -> HttpResponse:
    """
    Confirma y bloquea la selección de equipos del participante.

    Recibe los IDs de equipos seleccionados, valida el presupuesto
    y los premios individuales, y marca la selección como confirmada.
    """
    if request.user.is_staff or request.user.has_confirmed_selection:  # type: ignore[union-attr]
        return redirect("pool:dashboard")

    config = TournamentConfig.get()
    team_ids = request.POST.getlist("teams")
    predicted_mvp = request.POST.get("predicted_mvp", "").strip()
    predicted_top_scorer = request.POST.get("predicted_top_scorer", "").strip()
    predicted_best_goalkeeper = request.POST.get(
        "predicted_best_goalkeeper", ""
    ).strip()

    selected_teams = NationalTeam.objects.filter(id__in=team_ids)
    total_price = sum(t.price for t in selected_teams)

    if total_price > config.budget:
        teams = NationalTeam.objects.all().order_by("group", "name")
        return render(
            request,
            "pool/select_teams.html",
            {
                "teams": teams,
                "budget": config.budget,
                "error": f"Presupuesto superado: {total_price}🪙 / {config.budget}🪙",
            },
        )

    if not predicted_mvp or not predicted_top_scorer or not predicted_best_goalkeeper:
        teams = NationalTeam.objects.all().order_by("group", "name")
        return render(
            request,
            "pool/select_teams.html",
            {
                "teams": teams,
                "budget": config.budget,
                "error": "Debes rellenar los tres campos de predicciones individuales (MVP, Pichichi y Mejor portero).",
            },
        )

    participant, _ = Participant.objects.get_or_create(user=request.user)
    participant.teams.set(selected_teams)
    participant.predicted_mvp = predicted_mvp
    participant.predicted_top_scorer = predicted_top_scorer
    participant.predicted_best_goalkeeper = predicted_best_goalkeeper
    participant.save()

    request.user.has_confirmed_selection = True  # type: ignore[union-attr]
    request.user.save(update_fields=["has_confirmed_selection"])  # type: ignore[union-attr]

    return redirect("pool:dashboard")
