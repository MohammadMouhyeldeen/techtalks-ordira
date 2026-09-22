from django.shortcuts import redirect
from django.urls import Resolver404, resolve

from .models import User


class UserStatusMiddleware:
    """
    Restricts authenticated users based on their account status.

    ACTIVE users may continue normally.
    PENDING users are redirected to the pending approval page.
    SUSPENDED users are redirected to the suspended account page.
    """

    LOGOUT_URL_NAMES = {
        "accounts:logout",
        "admin:logout",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user

        if not user.is_authenticated:
            return self.get_response(request)

        current_view_name = self._get_current_view_name(request)

        # Users must always be able to log out.
        if current_view_name in self.LOGOUT_URL_NAMES:
            return self.get_response(request)

        if user.status == User.Status.PENDING:
            if current_view_name != "accounts:pending_approval":
                return redirect("accounts:pending_approval")

        elif user.status == User.Status.SUSPENDED:
            if current_view_name != "accounts:account_suspended":
                return redirect("accounts:account_suspended")

        return self.get_response(request)

    @staticmethod
    def _get_current_view_name(request):
        try:
            return resolve(request.path_info).view_name
        except Resolver404:
            return None