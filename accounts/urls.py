from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
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
]