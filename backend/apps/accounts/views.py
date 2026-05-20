"""Vistas de la app accounts (stub inicial)."""

from django.contrib.auth import authenticate, login
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.i18n import set_language as _django_set_language


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
            # Activar el idioma preferido del usuario en la sesión
            request.session["_language"] = user.preferred_language
            return redirect("pool:dashboard")
        error = _("Usuario o contraseña incorrectos.")

    return render(request, "accounts/login.html", {"error": error})


def set_language_view(request: HttpRequest) -> HttpResponse:
    """Cambia el idioma activo y lo persiste en el perfil del usuario autenticado."""
    response = _django_set_language(request)
    if request.user.is_authenticated and request.method == "POST":
        lang = request.POST.get("language")
        if lang in ("es", "eu"):
            request.user.preferred_language = lang
            request.user.save(update_fields=["preferred_language"])
    return response
