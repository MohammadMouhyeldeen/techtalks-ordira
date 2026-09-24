from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from shops.models import Shop

from .forms import CategoryForm, ProductForm, ProductVariantForm
from .models import Category, Product, ProductVariant
# ---------------------------------------------------------------------------
# DUMMY DATA — Sprint 2 placeholder for the public storefront pages.
#
# Shaped to match the real Category/Product/ProductVariant models in
# products/models.py so the swap to a real queryset later only touches this
# module, not the templates:
#
#   products = (
#       Product.objects.filter(shop=shop, is_active=True)
#       .select_related("category")
#       .annotate(price=Min("variants__unit_price"))
#   )
#
# The templates already iterate `products` / read `product.<field>` and
# never assume this dict shape beyond that.
#
# NOTE: "hex" on each variant is a display-only convenience (a swatch
# color) that has no equivalent on the real ProductVariant model yet —
# ProductVariant.color is free-text. Once real variants land, either add a
# color->hex lookup table or drop the color swatches for a text label.
# ---------------------------------------------------------------------------

DUMMY_PRODUCTS = [
    {
        "id": 1, "name": "Linen Shirt", "category": "Clothing", "price": "28.00",
        "swatch": 1, "badge": "",
        "description": "Breathable linen shirt with a relaxed fit — perfect for Beirut summers. Machine washable.",
        "variants": [
            {"color": "Sand", "hex": "#d8c3a5", "size": "S", "unit_price": "28.00", "stock_quantity": 5},
            {"color": "Sand", "hex": "#d8c3a5", "size": "M", "unit_price": "28.00", "stock_quantity": 8},
            {"color": "Sand", "hex": "#d8c3a5", "size": "L", "unit_price": "28.00", "stock_quantity": 0},
        ],
    },
    {
        "id": 2, "name": "Denim Jacket", "category": "Clothing", "price": "45.00",
        "swatch": 2, "badge": "Best seller", "badge_type": "best",
        "description": "Classic mid-wash denim jacket with brass buttons and a durable cotton lining.",
        "variants": [
            {"color": "Indigo", "hex": "#3b4d8f", "size": "S", "unit_price": "45.00", "stock_quantity": 6},
            {"color": "Indigo", "hex": "#3b4d8f", "size": "M", "unit_price": "45.00", "stock_quantity": 2},
            {"color": "Indigo", "hex": "#3b4d8f", "size": "L", "unit_price": "45.00", "stock_quantity": 0},
            {"color": "Black", "hex": "#22222a", "size": "M", "unit_price": "48.00", "stock_quantity": 9},
        ],
    },
    {
        "id": 3, "name": "Summer Dress", "category": "Clothing", "price": "32.00",
        "swatch": 3, "badge": "",
        "description": "Light floral dress with adjustable straps — easy to dress up or down.",
        "variants": [
            {"color": "Floral", "hex": "#e8a9c0", "size": "S", "unit_price": "32.00", "stock_quantity": 4},
            {"color": "Floral", "hex": "#e8a9c0", "size": "M", "unit_price": "32.00", "stock_quantity": 7},
        ],
    },
    {
        "id": 4, "name": "Tote Bag", "category": "Accessories", "price": "18.00",
        "swatch": 4, "badge": "",
        "description": "Durable canvas tote with an inner pocket — big enough for a full day out.",
        "variants": [
            {"color": "Natural", "hex": "#cbb994", "size": "One size", "unit_price": "18.00", "stock_quantity": 14},
        ],
    },
    {
        "id": 5, "name": "Silk Scarf", "category": "Accessories", "price": "22.00",
        "swatch": 1, "badge": "New", "badge_type": "new",
        "description": "Hand-finished silk scarf in a soft print. One size.",
        "variants": [
            {"color": "Blush", "hex": "#f3c9d6", "size": "One size", "unit_price": "22.00", "stock_quantity": 3},
        ],
    },
    {
        "id": 6, "name": "Wool Sweater", "category": "Clothing", "price": "38.00",
        "swatch": 2, "badge": "Low stock", "badge_type": "low",
        "description": "Cozy ribbed wool-blend sweater for cooler evenings.",
        "variants": [
            {"color": "Charcoal", "hex": "#4b4b52", "size": "S", "unit_price": "38.00", "stock_quantity": 1},
            {"color": "Charcoal", "hex": "#4b4b52", "size": "M", "unit_price": "38.00", "stock_quantity": 0},
        ],
    },
    {
        "id": 7, "name": "Leather Belt", "category": "Accessories", "price": "24.00",
        "swatch": 3, "badge": "",
        "description": "Genuine leather belt with a brushed brass buckle.",
        "variants": [
            {"color": "Brown", "hex": "#7a5230", "size": "M", "unit_price": "24.00", "stock_quantity": 10},
            {"color": "Brown", "hex": "#7a5230", "size": "L", "unit_price": "24.00", "stock_quantity": 6},
        ],
    },
    {
        "id": 8, "name": "Canvas Sneakers", "category": "Footwear", "price": "34.00",
        "swatch": 4, "badge": "New", "badge_type": "new",
        "description": "Everyday canvas sneakers with a cushioned insole.",
        "variants": [
            {"color": "White", "hex": "#f2f2f2", "size": "39", "unit_price": "34.00", "stock_quantity": 5},
            {"color": "White", "hex": "#f2f2f2", "size": "40", "unit_price": "34.00", "stock_quantity": 5},
            {"color": "White", "hex": "#f2f2f2", "size": "41", "unit_price": "34.00", "stock_quantity": 0},
        ],
    },
]


def public_catalog(request):
    return render(request, "storefront/public_catalog.html", {
        "products": DUMMY_PRODUCTS,
    })


def product_detail(request, pk):
    product = next((p for p in DUMMY_PRODUCTS if p["id"] == pk), None)
    if product is None:
        raise Http404("Product not found")

    related_products = [
        p for p in DUMMY_PRODUCTS
        if p["category"] == product["category"] and p["id"] != product["id"]
    ][:4]

    colors = []
    seen_colors = set()
    for variant in product["variants"]:
        if variant["color"] not in seen_colors:
            seen_colors.add(variant["color"])
            colors.append({"name": variant["color"], "hex": variant["hex"]})

    return render(request, "storefront/product_detail.html", {
        "product": product,
        "colors": colors,
        "related_products": related_products,
    })

def get_owner_shop(request, shop_pk):
    return get_object_or_404(
        Shop,
        pk=shop_pk,
        owner=request.user,
    )


@login_required
def category_list(request, shop_pk):
    shop = get_owner_shop(request, shop_pk)

    categories = Category.objects.filter(
        shop=shop,
        is_active=True,
    )

    return render(
        request,
        "products/category_list.html",
        {
            "shop": shop,
            "categories": categories,
        },
    )


@login_required
def category_create(request, shop_pk):
    shop = get_owner_shop(request, shop_pk)

    form = CategoryForm(
        request.POST or None,
        shop=shop,
    )

    if request.method == "POST" and form.is_valid():
        category = form.save(commit=False)
        category.shop = shop
        category.save()

        messages.success(request, "Category created successfully.")

        return redirect(
            "products:category-list",
            shop_pk=shop.pk,
        )

    return render(
        request,
        "products/category_form.html",
        {
            "shop": shop,
            "form": form,
            "page_title": "Create category",
        },
    )


@login_required
def category_edit(request, shop_pk, category_pk):
    shop = get_owner_shop(request, shop_pk)

    category = get_object_or_404(
        Category,
        pk=category_pk,
        shop=shop,
    )

    form = CategoryForm(
        request.POST or None,
        instance=category,
        shop=shop,
    )

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Category updated successfully.")

        return redirect(
            "products:category-list",
            shop_pk=shop.pk,
        )

    return render(
        request,
        "products/category_form.html",
        {
            "shop": shop,
            "category": category,
            "form": form,
            "page_title": "Edit category",
        },
    )


@login_required
@require_POST
def category_archive(request, shop_pk, category_pk):
    shop = get_owner_shop(request, shop_pk)

    category = get_object_or_404(
        Category,
        pk=category_pk,
        shop=shop,
        is_active=True,
    )

    category.is_active = False
    category.save(update_fields=["is_active"])

    messages.success(request, "Category archived successfully.")

    return redirect(
        "products:category-list",
        shop_pk=shop.pk,
    )

@login_required
def owner_product_list(request, shop_pk):
    shop = get_owner_shop(request, shop_pk)

    products = (
        Product.objects
        .filter(shop=shop, is_active=True)
        .select_related("category")
    )

    return render(
        request,
        "products/product_list.html",
        {
            "shop": shop,
            "products": products,
        },
    )


@login_required
def owner_product_detail(request, shop_pk, product_pk):
    shop = get_owner_shop(request, shop_pk)

    product = get_object_or_404(
        Product.objects.select_related("category"),
        pk=product_pk,
        shop=shop,
    )

    return render(
        request,
        "products/product_detail.html",
        {
            "shop": shop,
            "product": product,
        },
    )


@login_required
def owner_product_create(request, shop_pk):
    shop = get_owner_shop(request, shop_pk)

    product_instance = Product(shop=shop)

    form = ProductForm(
        request.POST or None,
        request.FILES or None,
        instance=product_instance,
        shop=shop,
    )

    if form.is_valid():
        product = form.save()
        messages.success(request, "Product created successfully.")

        return redirect(
            "products:product-detail",
            shop_pk=shop.pk,
            product_pk=product.pk,
        )

    return render(
        request,
        "products/product_form.html",
        {
            "shop": shop,
            "form": form,
            "page_title": "Create product",
        },
    )


@login_required
def owner_product_edit(request, shop_pk, product_pk):
    shop = get_owner_shop(request, shop_pk)

    product = get_object_or_404(
        Product,
        pk=product_pk,
        shop=shop,
    )

    form = ProductForm(
        request.POST or None,
        request.FILES or None,
        instance=product,
        shop=shop,
    )

    if form.is_valid():
        product = form.save()
        messages.success(request, "Product updated successfully.")

        return redirect(
            "products:product-detail",
            shop_pk=shop.pk,
            product_pk=product.pk,
        )

    return render(
        request,
        "products/product_form.html",
        {
            "shop": shop,
            "product": product,
            "form": form,
            "page_title": "Edit product",
        },
    )


@login_required
@require_POST
def owner_product_archive(request, shop_pk, product_pk):
    shop = get_owner_shop(request, shop_pk)

    product = get_object_or_404(
        Product,
        pk=product_pk,
        shop=shop,
    )

    product.is_active = False
    product.save(update_fields=["is_active"])

    messages.success(request, "Product archived successfully.")

    return redirect(
        "products:product-list",
        shop_pk=shop.pk,
    )

@login_required
def owner_variant_detail(request, shop_pk, product_pk, variant_pk):
    shop = get_owner_shop(request, shop_pk)

    product = get_object_or_404(
        Product,
        pk=product_pk,
        shop=shop,
    )

    variant = get_object_or_404(
        ProductVariant,
        pk=variant_pk,
        product=product,
    )

    return render(
        request,
        "products/variant_detail.html",
        {
            "shop": shop,
            "product": product,
            "variant": variant,
        },
    )


@login_required
def owner_variant_create(request, shop_pk, product_pk):
    shop = get_owner_shop(request, shop_pk)

    product = get_object_or_404(
        Product,
        pk=product_pk,
        shop=shop,
    )

    variant_instance = ProductVariant(product=product)

    form = ProductVariantForm(
        request.POST or None,
        instance=variant_instance,
        product=product,
    )

    if form.is_valid():
        variant = form.save()

        messages.success(
            request,
            "Product variant created successfully.",
        )

        return redirect(
            "products:variant-detail",
            shop_pk=shop.pk,
            product_pk=product.pk,
            variant_pk=variant.pk,
        )

    return render(
        request,
        "products/variant_form.html",
        {
            "shop": shop,
            "product": product,
            "form": form,
            "page_title": "Create product variant",
        },
    )


@login_required
def owner_variant_edit(request, shop_pk, product_pk, variant_pk):
    shop = get_owner_shop(request, shop_pk)

    product = get_object_or_404(
        Product,
        pk=product_pk,
        shop=shop,
    )

    variant = get_object_or_404(
        ProductVariant,
        pk=variant_pk,
        product=product,
    )

    form = ProductVariantForm(
        request.POST or None,
        instance=variant,
        product=product,
    )

    if form.is_valid():
        variant = form.save()

        messages.success(
            request,
            "Product variant updated successfully.",
        )

        return redirect(
            "products:variant-detail",
            shop_pk=shop.pk,
            product_pk=product.pk,
            variant_pk=variant.pk,
        )

    return render(
        request,
        "products/variant_form.html",
        {
            "shop": shop,
            "product": product,
            "variant": variant,
            "form": form,
            "page_title": "Edit product variant",
        },
    )


@login_required
@require_POST
def owner_variant_delete(request, shop_pk, product_pk, variant_pk):
    shop = get_owner_shop(request, shop_pk)

    product = get_object_or_404(
        Product,
        pk=product_pk,
        shop=shop,
    )

    variant = get_object_or_404(
        ProductVariant,
        pk=variant_pk,
        product=product,
    )

    variant.delete()

    messages.success(
        request,
        "Product variant deleted successfully.",
    )

    return redirect(
        "products:product-detail",
        shop_pk=shop.pk,
        product_pk=product.pk,
    )