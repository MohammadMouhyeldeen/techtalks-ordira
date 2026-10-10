from django.urls import path

from . import views


app_name = "payments"

urlpatterns = [
    path(
        "shops/<int:shop_pk>/orders/<int:order_pk>/record-payment/",
        views.record_order_payment,
        name="record-payment",
    ),
]
