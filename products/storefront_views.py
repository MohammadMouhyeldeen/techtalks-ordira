from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.db.models import Min
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect, render

from shops.decorators import public_shop_required

from . import cart
from .forms import CheckoutForm
from .models import Category, Product, ProductVariant


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


def _convert_amount(amount, from_currency, to_currency, rate):
    """Converts a USD/LBP amount using the shop's own fx rate (LBP per
    USD) — the same formula orders.services.create_order will use."""
    if from_currency == to_currency:
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if from_currency == "USD":
        converted = amount * rate
    else:
        converted = amount / rate
    return converted.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@public_shop_required
def cart_add(request, shop):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    variant = ProductVariant.objects.filter(
        pk=request.POST.get("variant_id"),
        is_active=True,
        product__is_active=True,
        product__shop=shop,
    ).select_related("product").first()

    if variant is None:
        messages.error(request, "That item is no longer available.")
        return redirect("public_catalog", shop.slug)

    try:
        quantity = max(1, int(request.POST.get("quantity", 1)))
    except (TypeError, ValueError):
        quantity = 1

    cart.add_item(request, shop, variant, quantity)
    messages.success(
        request,
        f"Added {quantity} × {variant.product.name} "
        f"({variant.color}, {variant.size}) to cart.",
    )
    return redirect("product_detail", shop.slug, variant.product_id)


@public_shop_required
def cart_view(request, shop):
    raw_count = cart.get_raw_count(request, shop)
    lines = cart.get_lines(request, shop)
    return render(request, "storefront/cart.html", {
        "shop": shop,
        "lines": lines,
        "totals": cart.get_totals(request, shop),
        "removed_count": raw_count - len(lines),
    })


@public_shop_required
def cart_update(request, shop):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        quantity = int(request.POST.get("quantity", 0))
    except (TypeError, ValueError):
        quantity = 0

    cart.update_item(request, shop, request.POST.get("variant_id"), quantity)
    return redirect("cart_view", shop.slug)


@public_shop_required
def cart_remove(request, shop):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    cart.remove_item(request, shop, request.POST.get("variant_id"))
    messages.success(request, "Item removed from cart.")
    return redirect("cart_view", shop.slug)


@public_shop_required
def checkout(request, shop):
    lines = cart.get_lines(request, shop)
    if not lines:
        messages.info(request, "Your cart is empty.")
        return redirect("cart_view", shop.slug)

    form = CheckoutForm(request.POST or None, shop=shop)

    if request.method == "POST" and form.is_valid():
        currency = form.cleaned_data["currency"]
        rate = shop.exchange_rate_lbp_per_usd

        preview_items = []
        items_total = Decimal("0.00")
        for line in lines:
            variant = line["variant"]
            line_total = _convert_amount(
                line["line_total"], line["currency"], currency, rate
            )
            items_total += line_total
            preview_items.append({
                "product_name": variant.product.name,
                "color": variant.color,
                "size": variant.size,
                "quantity": line["quantity"],
                "unit_price": str(
                    (line_total / line["quantity"]).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                ),
                "line_total": str(line_total),
            })

        fulfillment_type = form.cleaned_data["fulfillment_type"]
        delivery_zone = form.cleaned_data.get("delivery_zone")
        zone_name = ""
        delivery_fee = Decimal("0.00")
        if fulfillment_type == "DELIVERY" and delivery_zone:
            zone_name = delivery_zone.area_name
            delivery_fee = _convert_amount(
                delivery_zone.fee, "USD", currency, rate
            )

        request.session["checkout_preview"] = {
            "customer_name": form.cleaned_data["customer_name"],
            "customer_phone": form.cleaned_data["customer_phone"],
            "fulfillment_type": fulfillment_type,
            "zone_name": zone_name,
            "address": form.cleaned_data.get("address", ""),
            "payment_method_display": (
                form.cleaned_data["selected_payment_method"]
                .get_method_name_display()
            ),
            "currency": currency,
            "items_total": str(items_total),
            "delivery_fee": str(delivery_fee),
            "total": str(items_total + delivery_fee),
            "items": preview_items,
        }
        request.session.modified = True

        return redirect("order_success", shop.slug)

    return render(request, "storefront/checkout.html", {
        "shop": shop,
        "form": form,
        "lines": lines,
        "totals": cart.get_totals(request, shop),
    })
