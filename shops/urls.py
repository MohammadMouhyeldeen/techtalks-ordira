from django.urls import path
from . import views

app_name = "shops"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("setup/", views.shop_setup, name="setup"),
]