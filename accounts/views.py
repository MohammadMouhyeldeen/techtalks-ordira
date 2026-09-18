from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

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


def _require_admin(request):
    """
    Returns a redirect response if the requesting user is not an ADMIN,
    or None if access should proceed.

    Non-admins (e.g. SHOP_OWNERs who hit an admin URL) are sent to their
    own correct destination via _get_redirect_url_for_user(), consistent
    with the role-redirect logic established in SCRUM-39.
    """
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if request.user.role != User.Role.ADMIN:
        return redirect(_get_redirect_url_for_user(request.user))
    return None


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
    """
    Lists all PENDING self-registered users for admin review.

    Role enforcement: only ADMIN users may access this view.
    A non-admin who reaches this URL is redirected to their own correct
    destination (SHOP_OWNER → shops:dashboard) — not to login — because
    they are already authenticated.
    """
    denied = _require_admin(request)
    if denied:
        return denied

    pending_qs = (
        User.objects
        .filter(status=User.Status.PENDING)
        .order_by("-date_joined")
    )
    paginator = Paginator(pending_qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "accounts/admin_dashboard.html", {"page_obj": page_obj})


@login_required
def approve_user(request, user_id):
    """
    Transitions a PENDING user → ACTIVE.

    POST-only. Guards the race condition: acquires a row-level lock via
    select_for_update() and re-checks the target's status is still PENDING
    before committing the transition, so two concurrent admin clicks cannot
    double-process the same row.
    """
    denied = _require_admin(request)
    if denied:
        return denied

    if request.method != "POST":
        return redirect("accounts:admin_dashboard")

    with transaction.atomic():
        target = get_object_or_404(
            User.objects.select_for_update(),
            pk=user_id,
        )

        if target.status != User.Status.PENDING:
            messages.error(
                request,
                f"{target.full_name} ({target.email}) is no longer pending "
                f"(current status: {target.get_status_display()}). No change made.",
            )
            return redirect("accounts:admin_dashboard")

        target.status = User.Status.ACTIVE
        target.save(update_fields=["status"])

    messages.success(
        request,
        f"{target.full_name} ({target.email}) has been approved and is now active.",
    )
    return redirect("accounts:admin_dashboard")


@login_required
def reject_user(request, user_id):
    """
    Transitions a PENDING user → SUSPENDED.

    The UI label is "Reject" for PENDING rows; the underlying status value
    is SUSPENDED — the same transition that would be used to suspend an
    already-ACTIVE user elsewhere in the app (future reuse point).

    POST-only. Same select_for_update() race-condition guard as approve_user.
    """
    denied = _require_admin(request)
    if denied:
        return denied

    if request.method != "POST":
        return redirect("accounts:admin_dashboard")

    with transaction.atomic():
        target = get_object_or_404(
            User.objects.select_for_update(),
            pk=user_id,
        )

        if target.status != User.Status.PENDING:
            messages.error(
                request,
                f"{target.full_name} ({target.email}) is no longer pending "
                f"(current status: {target.get_status_display()}). No change made.",
            )
            return redirect("accounts:admin_dashboard")

        target.status = User.Status.SUSPENDED
        target.save(update_fields=["status"])

    messages.success(
        request,
        f"{target.full_name} ({target.email}) has been rejected and their account suspended.",
    )
    return redirect("accounts:admin_dashboard")