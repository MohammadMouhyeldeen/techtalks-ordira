from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Max
from django.shortcuts import get_object_or_404, render

from shops.models import Shop

from .models import Customer


def _get_owner_shop(request, shop_pk):
    return get_object_or_404(
        Shop,
        pk=shop_pk,
        owner=request.user,
    )


@login_required
def customer_list(request, shop_pk):
    shop = _get_owner_shop(request, shop_pk)

    customers = (
        Customer.objects
        .filter(shop=shop)
        .annotate(
            order_count=Count("orders"),
            last_order_at=Max("orders__created_at"),
        )
        .order_by(F("last_order_at").desc(nulls_last=True), "full_name")
    )

    return render(request, "customers/customer_list.html", {
        "shop": shop,
        "customers": customers,
    })


@login_required
def customer_detail(request, shop_pk, customer_pk):
    shop = _get_owner_shop(request, shop_pk)
    customer = get_object_or_404(Customer, pk=customer_pk, shop=shop)

    orders = customer.orders.order_by("-created_at")

    return render(request, "customers/customer_detail.html", {
        "shop": shop,
        "customer": customer,
        "orders": orders,
    })
