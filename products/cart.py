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
for display. The one exception is a basic stock ceiling in add_item: a
cart quantity is clamped so it can never exceed the variant's current
stock, independent of whatever the calling view already checked.

Read-only peeks (_cart/_bucket) use plain dict .get() rather than
setdefault(), so a GET request that never touches the cart (browsing the
catalog, a product page, even an empty cart page) never creates a session
row or sets a cookie for that visitor. Only add_item actually creates the
session/bucket structure; update_item and remove_item only ever modify a
key that's already present — they can't be used to plant an unresolvable
entry into someone's session.
"""
from collections import defaultdict
from decimal import Decimal

from .models import ProductVariant

SESSION_KEY = "cart"


def _cart(request):
    """Read-only peek at the whole cart — never creates a session row."""
    return request.session.get(SESSION_KEY, {})


def _bucket(request, shop):
    """Read-only peek at one shop's bucket — never creates a session row."""
    return _cart(request).get(str(shop.pk), {})


def add_item(request, shop, variant, quantity=1):
    quantity = min(quantity, variant.stock_quantity)
    if quantity <= 0:
        return

    cart = request.session.setdefault(SESSION_KEY, {})
    bucket = cart.setdefault(str(shop.pk), {})
    key = str(variant.pk)
    bucket[key] = min(bucket.get(key, 0) + quantity, variant.stock_quantity)
    request.session.modified = True


def update_item(request, shop, variant_id, quantity):
    """Only ever touches a key that's already in the bucket — this can
    update or remove an existing line, but never create a new one, so a
    bogus variant_id can't poison the session."""
    bucket = _bucket(request, shop)
    key = str(variant_id)

    if key not in bucket:
        return

    if quantity <= 0:
        del bucket[key]
    else:
        bucket[key] = quantity

    request.session.modified = True


def remove_item(request, shop, variant_id):
    bucket = _bucket(request, shop)
    key = str(variant_id)

    if key in bucket:
        del bucket[key]
        request.session.modified = True


def get_lines(request, shop):
    bucket = _bucket(request, shop)
    if not bucket:
        return []

    variant_ids = set()
    stale_keys = []
    for key in bucket:
        try:
            variant_ids.add(int(key))
        except (TypeError, ValueError):
            # A key that isn't even a valid variant id — can't happen via
            # add_item/update_item's own guards, but treat defensively as
            # stale rather than letting int(key) blow up below.
            stale_keys.append(key)

    variants = ProductVariant.objects.filter(
        pk__in=variant_ids,
        is_active=True,
        product__is_active=True,
        product__shop_id=shop.pk,
    ).select_related("product")
    variants_by_id = {variant.pk: variant for variant in variants}

    lines = []
    for key, quantity in bucket.items():
        if key in stale_keys:
            continue

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
    removed = cart.pop(str(shop.pk), None)
    if removed is not None:
        request.session.modified = True
