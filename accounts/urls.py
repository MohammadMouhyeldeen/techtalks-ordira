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
]