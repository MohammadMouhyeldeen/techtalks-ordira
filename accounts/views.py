import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import PasswordResetCompleteView, PasswordResetConfirmView
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .forms import AdminCreateUserForm, LoginForm, RegistrationForm
from .models import User

logger = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# SCRUM-41: Admin direct user creation + one-time set-password link
# ---------------------------------------------------------------------------

#: Session key used to pass the newly created user's pk from admin_create_user
#: to admin_link_display.  Only the pk (an integer) is stored — never the link,
#: token, or uid-b64.  The key is popped on first render so reload shows nothing.
_LINK_UID_SESSION_KEY = "_scrum41_link_uid"


@login_required
def admin_create_user(request):
    """
    Admin-only form to create a user directly (SCRUM-41).

    GET  → render the blank form.
    POST → validate, create user with unusable password, store target uid in
           the session, redirect to admin_link_display (shows the link once).

    Role gate: _require_admin() redirects non-admins before view logic runs.
    Status gate: UserStatusMiddleware handles PENDING / SUSPENDED before this.
    """
    denied = _require_admin(request)
    if denied:
        return denied

    if request.method == "POST":
        form = AdminCreateUserForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]        # already stripped + lower-cased
            full_name = form.cleaned_data["full_name"]
            role = form.cleaned_data["role"]

            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        email=email,
                        password=None,                # unusable password (AC4, AC8)
                        full_name=full_name,
                        role=role,
                        status=User.Status.ACTIVE,    # bypass approval flow (AC4)
                    )
            except IntegrityError:
                # Two admins created the same email at the same moment (AC11).
                form.add_error(
                    "email",
                    "A user with this email already exists.",
                )
            else:
                # AC12: one log line — never logs the link, token, uid-b64, or password.
                logger.info(
                    "admin_create uid=%s role=%s by_admin=%s",
                    user.pk,
                    user.role,
                    request.user.pk,
                )
                # Store only the pk (integer) in the session; the link is
                # generated at render time in admin_link_display (AC6, Amendment 1).
                request.session[_LINK_UID_SESSION_KEY] = user.pk
                return redirect("accounts:admin_link_display")
    else:
        form = AdminCreateUserForm()

    return render(request, "accounts/admin_create_user.html", {"form": form})


@login_required
def admin_link_display(request):
    """
    Displays the one-time set-password link to the acting Admin (SCRUM-41).

    The link is generated here from the session-stored uid; the session key is
    popped immediately so a reload or back-button shows nothing (AC6).

    The target user's ACTIVE status is re-checked before rendering:
    if the user was deactivated/suspended between creation and this GET,
    no link is shown and the Admin is redirected back (AC, amendment).
    """
    denied = _require_admin(request)
    if denied:
        return denied

    if request.method != "GET":
        return redirect("accounts:admin_create_user")

    uid = request.session.pop(_LINK_UID_SESSION_KEY, None)
    if uid is None:
        # Reload, back-button, or direct GET — no link to show.
        return redirect("accounts:admin_create_user")

    # Fetch the target; 404 is a safe fallback (pk was just stored by this session).
    target = get_object_or_404(User, pk=uid)

    # Re-check status: if the target is no longer ACTIVE, refuse to show a link.
    if target.status != User.Status.ACTIVE:
        messages.error(
            request,
            f"{target.full_name} ({target.email}) is no longer active "
            f"(status: {target.get_status_display()}). No link generated.",
        )
        return redirect("accounts:admin_create_user")

    # Build the set-password link using Django built-ins only (AC5).
    uid_b64 = urlsafe_base64_encode(force_bytes(target.pk))
    token = default_token_generator.make_token(target)
    link = request.build_absolute_uri(
        reverse("accounts:set_password", args=[uid_b64, token])
    )

    expire_days = settings.PASSWORD_RESET_TIMEOUT // 86400
    response = render(
        request,
        "accounts/admin_link_display.html",
        {"target": target, "link": link, "expire_days": expire_days},
    )
    # AC6: prevent caching so the link is not retrievable from browser history.
    response["Cache-Control"] = "no-store"
    return response


class SetPasswordView(PasswordResetConfirmView):
    """
    Lets the new user choose their password via the one-time link (SCRUM-41).

    Subclasses Django's PasswordResetConfirmView:
    - Token validity and single-use behaviour handled by the parent (AC7).
    - Password validators enforced by SetPasswordForm via parent (AC7).
    - Token moved out of the URL into the session by the parent (AC7).
    - No auto-login after success (post_reset_login=False, the default) (AC7).
    - validlink=False in template context when link is bad (Amendment 3).
    """

    template_name = "accounts/set_password.html"
    success_url = reverse_lazy("accounts:set_password_complete")
    # Do not log the user in automatically after they set a password (AC7).
    post_reset_login = False


class SetPasswordCompleteView(PasswordResetCompleteView):
    """
    Confirms that the password was set; shows a Log In button (Amendment 2).

    Standalone page — does not use admin_base.html because the visitor is the
    new user, not the Admin.
    """

    template_name = "accounts/set_password_complete.html"
