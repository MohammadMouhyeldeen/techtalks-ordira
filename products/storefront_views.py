from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Min
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect, render

from orders.services import create_order
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


@public_shop_required
def cart_add(request, shop):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        variant_id = int(request.POST.get("variant_id"))
    except (TypeError, ValueError):
        messages.error(request, "That item is no longer available.")
        return redirect("public_catalog", shop.slug)

    variant = ProductVariant.objects.filter(
        pk=variant_id,
        is_active=True,
        product__is_active=True,
        product__shop=shop,
    ).select_related("product").first()

    if variant is None:
        messages.error(request, "That item is no longer available.")
        return redirect("public_catalog", shop.slug)

    if variant.stock_quantity <= 0:
        messages.error(request, "That item is currently out of stock.")
        return redirect("product_detail", shop.slug, variant.product_id)

    try:
        quantity = max(1, int(request.POST.get("quantity", 1)))
    except (TypeError, ValueError):
        quantity = 1
    quantity = min(quantity, variant.stock_quantity)

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
        variant_id = int(request.POST.get("variant_id"))
    except (TypeError, ValueError):
        return redirect("cart_view", shop.slug)

    try:
        quantity = int(request.POST.get("quantity", 0))
    except (TypeError, ValueError):
        quantity = 0

    variant = ProductVariant.objects.filter(
        pk=variant_id,
        is_active=True,
        product__is_active=True,
        product__shop=shop,
    ).first()

    if variant is None:
        # No longer resolvable — drop the stale line instead of trying
        # to store a quantity for it.
        cart.remove_item(request, shop, variant_id)
        return redirect("cart_view", shop.slug)

    if quantity > 0:
        quantity = min(quantity, variant.stock_quantity)

    cart.update_item(request, shop, variant_id, quantity)
    return redirect("cart_view", shop.slug)


@public_shop_required
def cart_remove(request, shop):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        variant_id = int(request.POST.get("variant_id"))
    except (TypeError, ValueError):
        return redirect("cart_view", shop.slug)

    cart.remove_item(request, shop, variant_id)
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
        items = [
            {"variant_id": line["variant"].pk, "quantity": line["quantity"]}
            for line in lines
        ]

        try:
            order = create_order(
                shop=shop,
                customer_name=form.cleaned_data["customer_name"],
                customer_phone=form.cleaned_data["customer_phone"],
                fulfillment_type=form.cleaned_data["fulfillment_type"],
                selected_payment_method=form.cleaned_data["selected_payment_method"],
                items=items,
                currency=form.cleaned_data["currency"],
                delivery_zone=form.cleaned_data.get("delivery_zone"),
                address=form.cleaned_data.get("address", ""),
            )
        except ValidationError as exc:
            for message in exc.messages:
                form.add_error(None, message)
        else:
            cart.clear(request, shop)
            return redirect("order_success", shop.slug, order.tracking_token)

    return render(request, "storefront/checkout.html", {
        "shop": shop,
        "form": form,
        "lines": lines,
        "totals": cart.get_totals(request, shop),
    })
