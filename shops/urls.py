from django.urls import path

from . import views

app_name = "shops"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("setup/", views.shop_setup, name="setup"),
    path("settings/", views.shop_settings, name="settings"),

    path(
        "admin/subscriptions/",
        views.subscription_list,
        name="subscription-list",
    ),
    path(
        "admin/subscriptions/shop/<int:shop_pk>/create/",
        views.subscription_create,
        name="subscription-create",
    ),
    path(
        "admin/subscriptions/<int:subscription_pk>/edit/",
        views.subscription_edit,
        name="subscription-edit",
    ),
]
