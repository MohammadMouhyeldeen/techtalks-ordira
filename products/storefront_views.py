from django.db.models import Min
from django.shortcuts import render

from shops.decorators import public_shop_required

from .models import Category, Product


def _catalog_products(shop):
    """Active, priced products for a shop. Shared by the catalog list and
    the product-detail page's related-products query."""
    return (
        Product.objects.filter(shop=shop, is_active=True)
        .select_related("category")
        .annotate(price=Min("variants__unit_price"))
        .exclude(price__isnull=True)
    )


@public_shop_required
def public_catalog(request, shop):
    products = _catalog_products(shop)

    categories = (
        Category.objects.filter(
            shop=shop,
            is_active=True,
            products__is_active=True,
        )
        .distinct()
        .order_by("name")
    )

    return render(request, "storefront/public_catalog.html", {
        "shop": shop,
        "products": products,
        "categories": categories,
    })


@public_shop_required
def product_detail(request, shop, product_pk):
    try:
        product = (
            Product.objects.select_related("category")
            .prefetch_related("variants")
            .get(pk=product_pk, shop=shop, is_active=True)
        )
    except Product.DoesNotExist:
        return render(
            request,
            "storefront/unavailable.html",
            {"state": "product_not_found", "shop": shop},
            status=404,
        )

    colors = []
    seen_colors = set()
    for variant in product.variants.all():
        if variant.color not in seen_colors:
            seen_colors.add(variant.color)
            colors.append({"name": variant.color})

    related_products = (
        _catalog_products(shop)
        .filter(category=product.category)
        .exclude(pk=product.pk)[:4]
    )

    return render(request, "storefront/product_detail.html", {
        "shop": shop,
        "product": product,
        "colors": colors,
        "related_products": related_products,
    })
