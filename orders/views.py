from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from shops.decorators import public_shop_required
from shops.models import Shop

from .models import Order


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
        "order_items": order.items.select_related("variant"),
        "payment_method_display": order.selected_payment_method.get_method_name_display(),
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