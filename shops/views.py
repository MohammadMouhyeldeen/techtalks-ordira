from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import User
from orders.models import Order

from .forms import (
    DeliveryZoneForm,
    PaymentMethodSettingsForm,
    ShopSettingsForm,
    ShopSetupForm,
    SubscriptionForm,
)
from .helpers import get_dashboard_stats, is_catalog_public, subscription_status
from .models import DeliveryZone, Shop, Subscription, ShopPaymentMethod





@login_required
def shop_settings(request):
    shop = request.user.shops.first()

    if shop is None:
        return redirect("shops:setup")

    if request.method == "POST":
        form = ShopSettingsForm(request.POST, request.FILES, instance=shop)

        if form.is_valid():
            form.save()
            messages.success(request, "Shop settings updated.")
            return redirect("shops:settings")
    else:
        form = ShopSettingsForm(instance=shop)

    return render(request, "shops/settings.html", {"form": form, "shop": shop})



@login_required
def payment_method_settings(request, shop_pk):
    shop = get_owner_shop(request, shop_pk)

    form = PaymentMethodSettingsForm(
        request.POST or None,
        shop=shop,
    )

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            "Payment methods updated.",
        )
        return redirect(
            "shops:payment-method-settings",
            shop_pk=shop.pk,
        )

    return render(
        request,
        "shops/payment_method_settings.html",
        {
            "shop": shop,
            "form": form,
        },
    )


@login_required
def shop_setup(request):
    if request.user.role != User.Role.SHOP_OWNER:
        return redirect("accounts:admin_dashboard")

    if request.user.shops.exists():
        return redirect("shops:dashboard")

    if request.method == "POST":
        form = ShopSetupForm(request.POST, request.FILES)

        if form.is_valid():
            shop = form.save(commit=False)
            shop.owner = request.user
            with transaction.atomic():
                shop.save()
                ShopPaymentMethod.objects.create(
                    shop=shop,
                    method_name=ShopPaymentMethod.MethodName.CASH,
                    enabled=True,
                )

            return redirect("shops:dashboard")
    else:
        form = ShopSetupForm()

    return render(request, "shops/shop_setup.html", {"form": form})


def _require_admin(request):
    if request.user.role != User.Role.ADMIN:
        return HttpResponseForbidden("Admin access required.")

    return None

def get_owner_shop(request, shop_pk):
    return get_object_or_404(
        Shop,
        pk=shop_pk,
        owner=request.user,
    )


@login_required
def subscription_list(request):
    access_denied = _require_admin(request)

    if access_denied:
        return access_denied

    shops = Shop.objects.select_related("owner").order_by("name")

    active_subscriptions = (
        Subscription.objects
        .filter(status=Subscription.Status.ACTIVE)
        .order_by("-starts_on", "-id")
        .select_related("shop")
    )

    non_active_subscriptions = (
        Subscription.objects
        .exclude(status=Subscription.Status.ACTIVE)
        .order_by("-starts_on", "-id")
        .select_related("shop")
    )

    subscription_by_shop = {}
    has_active_by_shop = {}

    for subscription in active_subscriptions:
        shop_id = subscription.shop_id
        if shop_id not in subscription_by_shop:
            subscription_by_shop[shop_id] = subscription
        has_active_by_shop[shop_id] = True

    for subscription in non_active_subscriptions:
        shop_id = subscription.shop_id
        if shop_id not in subscription_by_shop:
            subscription_by_shop[shop_id] = subscription

    shop_rows = []

    for shop in shops:
        shop_rows.append(
            {
                "shop": shop,
                "subscription": subscription_by_shop.get(shop.id),
                "has_active": has_active_by_shop.get(shop.id, False),
            }
        )

    return render(
        request,
        "shops/subscription_list.html",
        {
            "shop_rows": shop_rows,
        },
    )


@login_required
def subscription_create(request, shop_pk):
    access_denied = _require_admin(request)

    if access_denied:
        return access_denied

    shop = get_object_or_404(Shop, pk=shop_pk)

    if request.method == "POST":
        form = SubscriptionForm(request.POST, shop=shop)

        if form.is_valid():
            subscription = form.save(commit=False)
            subscription.shop = shop
            try:
                with transaction.atomic():
                    subscription.save()
            except IntegrityError:
                form.add_error(None, "This shop already has an active subscription.")
            else:
                return redirect("shops:subscription-list")
    else:
        form = SubscriptionForm(shop=shop)

    return render(
        request,
        "shops/subscription_form.html",
        {
            "form": form,
            "shop": shop,
            "page_title": "Create Subscription",
        },
    )


@login_required
def subscription_edit(request, subscription_pk):
    access_denied = _require_admin(request)

    if access_denied:
        return access_denied

    subscription = get_object_or_404(
        Subscription.objects.select_related("shop"),
        pk=subscription_pk,
    )

    if request.method == "POST":
        form = SubscriptionForm(
            request.POST,
            instance=subscription,
            shop=subscription.shop,
        )

        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
            except IntegrityError:
                form.add_error(None, "This shop already has an active subscription.")
            else:
                return redirect("shops:subscription-list")
    else:
        form = SubscriptionForm(instance=subscription, shop=subscription.shop)

    return render(
        request,
        "shops/subscription_form.html",
        {
            "form": form,
            "shop": subscription.shop,
            "subscription": subscription,
            "page_title": "Edit Subscription",
        },
    )


@login_required
def dashboard(request):
    if (
        request.user.role == User.Role.SHOP_OWNER
        and not request.user.shops.exists()
    ):
        return redirect("shops:setup")

    shop = request.user.shops.first()

    stats = (
        get_dashboard_stats(shop)
        if shop is not None
        else {
            "total_products": 0,
            "total_variants": 0,
            "low_stock_count": 0,
        }
    )

    has_active_subscription = (
        is_catalog_public(shop)
        if shop is not None
        else False
    )

    subscription_status_value = (
        subscription_status(shop)
        if shop is not None
        else "NONE"
    )

    is_shop_owner = request.user.role == User.Role.SHOP_OWNER

    return render(
        request,
        "shops/dashboard.html",
        {
            **stats,
            "has_active_subscription": has_active_subscription,
            "subscription_status": subscription_status_value,
            "is_shop_owner": is_shop_owner,
        },
    )


@login_required
def delivery_zone_list(request, shop_pk):
    shop = get_owner_shop(request, shop_pk)

    zones = DeliveryZone.objects.filter(
        shop=shop,
    )

    return render(
        request,
        "shops/delivery_zone_list.html",
        {
            "shop": shop,
            "zones": zones,
        },
    )


@login_required
def delivery_zone_create(request, shop_pk):
    shop = get_owner_shop(request, shop_pk)

    form = DeliveryZoneForm(
        request.POST or None,
        shop=shop,
    )

    if request.method == "POST" and form.is_valid():
        zone = form.save(commit=False)
        zone.shop = shop
        zone.save()

        messages.success(
            request,
            "Delivery zone created successfully.",
        )

        return redirect(
            "shops:delivery-zone-list",
            shop_pk=shop.pk,
        )

    return render(
        request,
        "shops/delivery_zone_form.html",
        {
            "shop": shop,
            "form": form,
            "page_title": "Create delivery zone",
        },
    )


@login_required
def delivery_zone_edit(request, shop_pk, zone_pk):
    shop = get_owner_shop(request, shop_pk)

    zone = get_object_or_404(
        DeliveryZone,
        pk=zone_pk,
        shop=shop,
    )

    form = DeliveryZoneForm(
        request.POST or None,
        instance=zone,
        shop=shop,
    )

    if request.method == "POST" and form.is_valid():
        form.save()

        messages.success(
            request,
            "Delivery zone updated successfully.",
        )

        return redirect(
            "shops:delivery-zone-list",
            shop_pk=shop.pk,
        )

    return render(
        request,
        "shops/delivery_zone_form.html",
        {
            "shop": shop,
            "zone": zone,
            "form": form,
            "page_title": "Edit delivery zone",
        },
    )


@login_required
@require_POST
def delivery_zone_delete(request, shop_pk, zone_pk):
    shop = get_owner_shop(request, shop_pk)
    zone = get_object_or_404(
        DeliveryZone,
        pk=zone_pk,
        shop=shop,
    )

    if Order.objects.filter(delivery_zone=zone).exists():
        messages.warning(
            request,
            "This delivery zone is used by existing orders. "
            "Deactivate it instead of deleting it.",
        )
        return redirect(
            "shops:delivery-zone-list",
            shop_pk=shop.pk,
        )

    zone.delete()
    messages.success(request, "Delivery zone deleted successfully.")
    return redirect(
        "shops:delivery-zone-list",
        shop_pk=shop.pk,
    )
