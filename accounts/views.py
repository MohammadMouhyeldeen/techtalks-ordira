from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import LoginForm, RegistrationForm
from .models import User


def _get_redirect_url_for_user(user):
    """Return the appropriate redirect URL based on role and status."""
    if user.status == User.Status.PENDING:
        return "accounts:pending_approval"
    if user.status == User.Status.SUSPENDED:
        return "accounts:account_suspended"
    if user.role == User.Role.ADMIN:
        return "accounts:admin_dashboard"
    return "shops:dashboard"


def register_view(request):
    if request.user.is_authenticated:
        return redirect(_get_redirect_url_for_user(request.user))

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("accounts:pending_approval")
    else:
        form = RegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect(_get_redirect_url_for_user(request.user))

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            login(request, form.user)
            return redirect(_get_redirect_url_for_user(form.user))
    else:
        form = LoginForm()

    return render(request, "accounts/login.html", {"form": form})


def logout_view(request):
    if request.method == "POST":
        logout(request)
    return redirect("accounts:login")


def pending_approval(request):
    return render(request, "accounts/pending_approval.html")


def account_suspended(request):
    return render(request, "accounts/account_suspended.html")


@login_required
def admin_dashboard(request):
    return render(request, "accounts/admin_dashboard.html")