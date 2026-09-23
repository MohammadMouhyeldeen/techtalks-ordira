from django.urls import path

from . import views

app_name = "products"

urlpatterns = [
    path(
        "shops/<int:shop_pk>/categories/",
        views.category_list,
        name="category-list",
    ),
    path(
        "shops/<int:shop_pk>/categories/create/",
        views.category_create,
        name="category-create",
    ),
    path(
        "shops/<int:shop_pk>/categories/<int:category_pk>/edit/",
        views.category_edit,
        name="category-edit",
    ),
    path(
        "shops/<int:shop_pk>/categories/<int:category_pk>/archive/",
        views.category_archive,
        name="category-archive",
    ),
]