from django.urls import path

from . import views


app_name = "orders"

urlpatterns = [
    path(
        "shops/<int:shop_pk>/orders/",
        views.merchant_order_list,
        name="order-list",
    ),
    path(
        "shops/<int:shop_pk>/orders/<int:order_pk>/",
        views.merchant_order_detail,
        name="order-detail",
    ),
]