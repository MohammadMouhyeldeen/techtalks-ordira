from django.http import Http404
from django.shortcuts import render

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
