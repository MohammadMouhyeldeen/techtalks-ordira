from django.urls import path

from . import views

app_name = "customers"

urlpatterns = [
    path(
        "shops/<int:shop_pk>/customers/",
        views.customer_list,
        name="list",
    ),
    path(
        "shops/<int:shop_pk>/customers/<int:customer_pk>/",
        views.customer_detail,
        name="detail",
    ),
]
