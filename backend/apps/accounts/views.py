"""Vistas de la app accounts (stub inicial)."""

from django.contrib.auth import authenticate, login
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render


def home(request: HttpRequest) -> HttpResponse:
    """Redirige al dashboard si está autenticado, si no al login."""
    if request.user.is_authenticated:
        return redirect("pool:dashboard")
    return redirect("accounts:login")


def login_view(request: HttpRequest) -> HttpResponse:
    """Página de login para usuarios normales y admin."""
    if request.user.is_authenticated:
        return redirect("pool:dashboard")

    error: str | None = None

    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("pool:dashboard")
        error = "Usuario o contraseña incorrectos."

    return render(request, "accounts/login.html", {"error": error})
