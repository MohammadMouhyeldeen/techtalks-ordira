from django.urls import path

from . import views

app_name = "products"

urlpatterns = [
    # Category CRUD
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

    # Product CRUD
    path(
        "shops/<int:shop_pk>/products/",
        views.owner_product_list,
        name="product-list",
    ),
    path(
        "shops/<int:shop_pk>/products/create/",
        views.owner_product_create,
        name="product-create",
    ),
    path(
        "shops/<int:shop_pk>/products/<int:product_pk>/",
        views.owner_product_detail,
        name="product-detail",
    ),
    path(
        "shops/<int:shop_pk>/products/<int:product_pk>/edit/",
        views.owner_product_edit,
        name="product-edit",
    ),
    path(
        "shops/<int:shop_pk>/products/<int:product_pk>/archive/",
        views.owner_product_archive,
        name="product-archive",
    ),
]