from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from shops.decorators import public_shop_required
from shops.models import Shop

from .models import Order


def _payment_method_display(order):
    """selected_payment_method is PROTECT + NOT NULL today, so a shop can't
    actually delete one out from under a placed order — but the guard is
    cheap insurance against that ever changing, and against a merchant
    somehow ending up with an order that has none."""
    method = getattr(order, "selected_payment_method", None)
    if method is None:
        return "Not available"
    return method.get_method_name_display()


def _order_context(order):
    """Shared context for both the one-time success page and the
    persistent tracking page — same order, same shape, so they can
    render through the same _order_overview.html partial.

    payment is read via getattr with a default rather than
    order.payment directly: Payment is a OneToOneField with no row
    created yet for most orders (SCRUM-78 records it after the fact),
    and Django's reverse one-to-one accessor raises DoesNotExist (a
    subclass of AttributeError) when there's no row — which is exactly
    what getattr's default argument is for."""
    return {
        "order_items": order.items.select_related("variant"),
        "payment_method_display": _payment_method_display(order),
        "payment": getattr(order, "payment", None),
    }


@public_shop_required
def order_success(request, shop, tracking_token):
    """Real order confirmation, looked up by tracking_token (an
    unguessable UUID) rather than pk — a sequential pk would let anyone
    enumerate other customers' orders and read their name/phone/address
    just by incrementing the URL."""
    order = get_object_or_404(
        Order.objects.select_related("selected_payment_method"),
        tracking_token=tracking_token,
        shop=shop,
    )

    return render(request, "storefront/order_success.html", {
        "shop": shop,
        "order": order,
        **_order_context(order),
    })


@public_shop_required
def track_order(request, shop, tracking_token):
    """Persistent "where's my order" page a customer can revisit any
    time, linked from the order-success page. Looked up by
    tracking_token + shop only — never by pk, for the same reason as
    order_success above."""
    order = get_object_or_404(
        Order.objects.select_related("selected_payment_method"),
        tracking_token=tracking_token,
        shop=shop,
    )

    return render(request, "storefront/order_tracking.html", {
        "shop": shop,
        "order": order,
        **_order_context(order),
    })


def _get_owner_shop(request, shop_pk):
    return get_object_or_404(
        Shop,
        pk=shop_pk,
        owner=request.user,
    )


@login_required
def merchant_order_list(request, shop_pk):
    shop = _get_owner_shop(request, shop_pk)

    orders = (
        Order.objects
        .filter(shop=shop)
        .select_related("customer")
        .order_by("-created_at")
    )

    selected_status = request.GET.get("status", "").strip()

    if selected_status in Order.Status.values:
        orders = orders.filter(status=selected_status)
    else:
        selected_status = ""

    return render(
        request,
        "orders/order_list.html",
        {
            "shop": shop,
            "orders": orders,
            "status_choices": Order.Status.choices,
            "selected_status": selected_status,
        },
    )


@login_required
def merchant_order_detail(request, shop_pk, order_pk):
    shop = _get_owner_shop(request, shop_pk)

    order = get_object_or_404(
        Order.objects
        .select_related(
            "customer",
            "delivery_zone",
            "selected_payment_method",
        )
        .prefetch_related("items"),
        pk=order_pk,
        shop=shop,
    )

    return render(
        request,
        "orders/order_detail.html",
        {
            "shop": shop,
            "order": order,
        },
    )
