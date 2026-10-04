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
    path(
        "shops/<int:shop_pk>/delivery-zones/",
        views.delivery_zone_list,
        name="delivery-zone-list",
    ),
    path(
        "shops/<int:shop_pk>/delivery-zones/create/",
        views.delivery_zone_create,
        name="delivery-zone-create",
    ),
    path(
        "shops/<int:shop_pk>/delivery-zones/<int:zone_pk>/edit/",
        views.delivery_zone_edit,
        name="delivery-zone-edit",
    ),
    path(
        "shops/<int:shop_pk>/delivery-zones/<int:zone_pk>/delete/",
        views.delivery_zone_delete,
        name="delivery-zone-delete",
    ),
]
