from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path(
        "pending-approval/",
        views.pending_approval,
        name="pending_approval",
    ),
    path(
        "account-suspended/",
        views.account_suspended,
        name="account_suspended",
    ),
    path(
        "admin-dashboard/",
        views.admin_dashboard,
        name="admin_dashboard",
    ),
    # SCRUM-40: Admin approval actions — POST-only, nested under admin-dashboard/
    path(
        "admin-dashboard/approve/<int:user_id>/",
        views.approve_user,
        name="approve_user",
    ),
    path(
        "admin-dashboard/reject/<int:user_id>/",
        views.reject_user,
        name="reject_user",
    ),
    # SCRUM-41: Admin direct user creation + one-time set-password link
    path(
        "admin-dashboard/create-user/",
        views.admin_create_user,
        name="admin_create_user",
    ),
    path(
        "admin-dashboard/link-display/",
        views.admin_link_display,
        name="admin_link_display",
    ),
    # SCRUM-41 Part B: Reissue link (POST-only, Admin only)
    path(
        "admin-dashboard/reissue/<int:user_id>/",
        views.admin_reissue_link,
        name="admin_reissue_link",
    ),
    # set-password/* lives outside admin-dashboard/ — visited by the new user, not the Admin.
    path(
        "set-password/<uidb64>/<token>/",
        views.SetPasswordView.as_view(),
        name="set_password",
    ),
    path(
        "set-password/done/",
        views.SetPasswordCompleteView.as_view(),
        name="set_password_complete",
    ),
]
