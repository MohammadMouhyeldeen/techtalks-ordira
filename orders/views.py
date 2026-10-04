from django.shortcuts import get_object_or_404, render

from shops.decorators import public_shop_required

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
