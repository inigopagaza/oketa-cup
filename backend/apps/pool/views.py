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
    # Si el usuario no ha confirmado selección, redirigir a seleccionar
    if not request.user.has_confirmed_selection:  # type: ignore[union-attr]
        return redirect("pool:select_teams")

    participant, _ = Participant.objects.get_or_create(user=request.user)

    # Clasificación general: todos los participantes ordenados por puntos
    ranking = sorted(
        Participant.objects.select_related("user").prefetch_related("teams"),
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

    return render(
        request,
        "pool/dashboard.html",
        {
            "participant": participant,
            "ranking": ranking,
            "todays_matches": todays_matches,
            "team_scores": team_scores,
        },
    )


@login_required
def select_teams(request: HttpRequest) -> HttpResponse:
    """
    Página de selección de equipos.

    Solo accesible si el usuario no ha confirmado su selección.
    Muestra todas las selecciones con precio y presupuesto restante.
    """
    if request.user.has_confirmed_selection:  # type: ignore[union-attr]
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
    if request.user.has_confirmed_selection:  # type: ignore[union-attr]
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

    participant, _ = Participant.objects.get_or_create(user=request.user)
    participant.teams.set(selected_teams)
    participant.predicted_mvp = predicted_mvp
    participant.predicted_top_scorer = predicted_top_scorer
    participant.predicted_best_goalkeeper = predicted_best_goalkeeper
    participant.save()

    request.user.has_confirmed_selection = True  # type: ignore[union-attr]
    request.user.save(update_fields=["has_confirmed_selection"])  # type: ignore[union-attr]

    return redirect("pool:dashboard")
