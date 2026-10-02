"""Session-backed shopping cart for the public storefront.

No database table — the cart lives entirely in request.session, nested by
shop so a browser session that visits two different shops keeps separate
carts:

    request.session["cart"] = {
        "<shop_id>": {"<variant_id>": quantity, ...},
        ...
    }

No price/stock validation lives here (that belongs to the real checkout
service, orders.services.create_order, once SCRUM-65 merges) — this module
only stores quantities and resolves them against live ProductVariant rows
for display.
"""
from collections import defaultdict
from decimal import Decimal

from .models import ProductVariant

SESSION_KEY = "cart"


def _cart(request):
    return request.session.setdefault(SESSION_KEY, {})


def _bucket(request, shop):
    cart = _cart(request)
    return cart.setdefault(str(shop.pk), {})


def add_item(request, shop, variant, quantity=1):
    bucket = _bucket(request, shop)
    key = str(variant.pk)
    bucket[key] = bucket.get(key, 0) + quantity
    request.session.modified = True


def update_item(request, shop, variant_id, quantity):
    bucket = _bucket(request, shop)
    key = str(variant_id)

    if quantity <= 0:
        bucket.pop(key, None)
    else:
        bucket[key] = quantity

    request.session.modified = True


def remove_item(request, shop, variant_id):
    bucket = _bucket(request, shop)
    bucket.pop(str(variant_id), None)
    request.session.modified = True


def get_lines(request, shop):
    bucket = _bucket(request, shop)
    if not bucket:
        return []

    variant_ids = [int(pk) for pk in bucket]
    variants = ProductVariant.objects.filter(
        pk__in=variant_ids,
        is_active=True,
        product__is_active=True,
        product__shop_id=shop.pk,
    ).select_related("product")
    variants_by_id = {variant.pk: variant for variant in variants}

    lines = []
    stale_keys = []
    for key, quantity in bucket.items():
        variant = variants_by_id.get(int(key))
        if variant is None:
            stale_keys.append(key)
            continue

        lines.append({
            "variant": variant,
            "quantity": quantity,
            "unit_price": variant.unit_price,
            "currency": variant.currency,
            "line_total": variant.unit_price * quantity,
        })

    if stale_keys:
        for key in stale_keys:
            bucket.pop(key, None)
        request.session.modified = True

    return lines


def get_raw_count(request, shop):
    """Count of distinct variant entries in the session bucket before
    resolving against the database — compare against len(get_lines(...))
    to detect how many were stale (deleted/deactivated/wrong-shop) and
    silently pruned."""
    return len(_bucket(request, shop))


def get_item_count(request, shop):
    return sum(line["quantity"] for line in get_lines(request, shop))


def get_totals(request, shop):
    totals = defaultdict(lambda: Decimal("0.00"))
    for line in get_lines(request, shop):
        totals[line["currency"]] += line["line_total"]
    return dict(totals)


def clear(request, shop):
    cart = _cart(request)
    cart.pop(str(shop.pk), None)
    request.session.modified = True
