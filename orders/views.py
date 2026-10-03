import uuid
from decimal import Decimal

from django.shortcuts import render
from django.utils import timezone

from shops.decorators import public_shop_required

from .models import Order, OrderItem


def _demo_order_number():
    return f"DEMO-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"


def _generic_dummy_order():
    order = Order(
        order_number="DEMO-00000",
        tracking_token=uuid.uuid4(),
        fulfillment_type=Order.FulfillmentType.DELIVERY,
        status=Order.Status.NEW,
        customer_name_snapshot="Jane Customer",
        customer_phone_snapshot="+961 70 123 456",
        zone_name_snapshot="Beirut",
        delivery_fee_snapshot=Decimal("3.00"),
        address_snapshot="Hamra Street, Beirut",
        items_total=Decimal("45.00"),
        total=Decimal("48.00"),
        currency=Order.Currency.USD,
        fx_rate_snapshot=Decimal("89500.00"),
        created_at=timezone.now(),
    )
    order_items = [
        OrderItem(
            product_name_snapshot="Denim Jacket",
            color_snapshot="Indigo",
            size_snapshot="M",
            unit_price_snapshot=Decimal("45.00"),
            quantity=1,
            line_total=Decimal("45.00"),
        ),
    ]
    return order, order_items, "Cash on delivery"


@public_shop_required
def order_success_preview(request, shop):
    """Order-success SHELL for Sprint 4 — no real order-creation service
    exists yet (SCRUM-65, blocked on a teammate's unmerged branch). This
    view is reached two ways: right after checkout's fake "submit" (real
    submitted data, stashed in the session and popped here — one-time, so
    a reload or a direct/bookmarked visit falls back to the generic
    example below), or that direct visit itself.

    Swap-in once orders.services.create_order exists: checkout's POST
    handler calls create_order(...) and redirects here with the real
    order's tracking_token (add a <uuid:tracking_token> segment to this
    URL) — NOT the pk. Sequential pks would let anyone enumerate other
    customers' orders by incrementing the URL and read their name/phone/
    address; tracking_token is an unguessable UUID, same pattern the
    model already uses for this exact purpose. This view then becomes
        order = get_object_or_404(Order, tracking_token=tracking_token, shop=shop)
        order_items = order.items.select_related("variant")
    The template needs ZERO changes — Order/OrderItem are real model
    classes here too (just unsaved), so it already reads the exact same
    attributes the real swapped-in queryset would return.
    """
    preview = request.session.pop("checkout_preview", None)

    if preview:
        order = Order(
            order_number=_demo_order_number(),
            tracking_token=uuid.uuid4(),
            fulfillment_type=preview["fulfillment_type"],
            status=Order.Status.NEW,
            customer_name_snapshot=preview["customer_name"],
            customer_phone_snapshot=preview["customer_phone"],
            zone_name_snapshot=preview["zone_name"],
            delivery_fee_snapshot=Decimal(preview["delivery_fee"]),
            address_snapshot=preview["address"],
            items_total=Decimal(preview["items_total"]),
            total=Decimal(preview["total"]),
            currency=preview["currency"],
            fx_rate_snapshot=shop.exchange_rate_lbp_per_usd,
            created_at=timezone.now(),
        )
        order_items = [
            OrderItem(
                product_name_snapshot=item["product_name"],
                color_snapshot=item["color"],
                size_snapshot=item["size"],
                unit_price_snapshot=Decimal(item["unit_price"]),
                quantity=item["quantity"],
                line_total=Decimal(item["line_total"]),
            )
            for item in preview["items"]
        ]
        payment_method_display = preview["payment_method_display"]
    else:
        order, order_items, payment_method_display = _generic_dummy_order()

    return render(request, "storefront/order_success.html", {
        "shop": shop,
        "order": order,
        "order_items": order_items,
        "payment_method_display": payment_method_display,
        "is_preview_fallback": preview is None,
    })
