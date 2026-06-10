"""Vistas de la app pool (stub inicial)."""

from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.tournament.models import Match, NationalTeam, TournamentConfig

from .models import Participant, ScoreLog


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
        .prefetch_related(
            "teams",
            Prefetch(
                "score_logs",
                queryset=ScoreLog.objects.select_related("team", "match").order_by(
                    "-created_at"
                ),
            ),
        )
        .filter(user__is_staff=False)
        .distinct(),
        key=lambda p: p.total_points,
        reverse=True,
    )

    # Precalcular puntos por selección para todos los participantes del ranking.
    team_points_rows = (
        ScoreLog.objects.filter(participant__in=ranking)
        .values("participant_id", "team_id")
        .annotate(total=Sum("points_earned"))
    )
    points_by_participant: dict[int, dict[int, int]] = {}
    for row in team_points_rows:
        points_by_participant.setdefault(row["participant_id"], {})[row["team_id"]] = (
            row["total"]
        )

    ranking_rows = []
    for ranked_participant in ranking:
        team_points = points_by_participant.get(ranked_participant.id, {})
        selections = [
            {
                "team": team,
                "points": team_points.get(team.id, 0),
            }
            for team in ranked_participant.teams.all()
        ]
        selections.sort(key=lambda entry: entry["points"], reverse=True)
        ranking_rows.append(
            {
                "participant": ranked_participant,
                "selections": selections,
                "score_logs": list(ranked_participant.score_logs.all()),
            }
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

    recent_score_logs = list(
        participant.score_logs.select_related("team", "match").order_by("-created_at")[
            :5
        ]
    )

    return render(
        request,
        "pool/dashboard.html",
        {
            "participant": participant,
            "ranking": ranking,
            "ranking_rows": ranking_rows,
            "todays_matches": todays_matches,
            "team_scores": team_scores,
            "recent_score_logs": recent_score_logs,
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
