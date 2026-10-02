
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, get_object_or_404
from django.http import HttpResponseForbidden

from accounts.models import User
from .forms import ShopSetupForm, ShopSettingsForm, SubscriptionForm
from .helpers import get_dashboard_stats, is_catalog_public
from .models import Shop, Subscription



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
            shop.save()

            return redirect("shops:dashboard")
    else:
        form = ShopSetupForm()

    return render(request, "shops/shop_setup.html", {"form": form})


def _require_admin(request):
    if request.user.role != User.Role.ADMIN:
        return HttpResponseForbidden("Admin access required.")

    return None


@login_required
def subscription_list(request):
    access_denied = _require_admin(request)

    if access_denied:
        return access_denied

    shops = Shop.objects.select_related("owner").order_by("name")

    subscriptions = (
        Subscription.objects
        .order_by("-starts_on", "-id")
        .select_related("shop")
    )

    subscription_by_shop = {}

    for subscription in subscriptions:
        current = subscription_by_shop.get(subscription.shop_id)

        if current is None:
            subscription_by_shop[subscription.shop_id] = subscription
        elif (
            subscription.status == Subscription.Status.ACTIVE
            and current.status != Subscription.Status.ACTIVE
        ):
            subscription_by_shop[subscription.shop_id] = subscription

    shop_rows = []

    for shop in shops:
        shop_rows.append(
            {
                "shop": shop,
                "subscription": subscription_by_shop.get(shop.id),
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
            subscription.save()

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
            form.save()

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
    subscription_status=None
    if shop is not None:
        active_subscription =(
            shop.subscriptions
            .filter(status=Subscription.Status.ACTIVE)
            .order_by("-starts_on", "-id")
            .first()
        )
        if active_subscription is not None:
            subscription_status = Subscription.Status.ACTIVE
        else:
            latest_subscription = (
                shop.subscriptions
                .order_by("-starts_on", "-id")
                .first()
            )
            if latest_subscription is not None:
                subscription_status = latest_subscription.status

    has_active_subscription = (
        subscription_status == Subscription.Status.ACTIVE
    )

    is_shop_owner = request.user.role == User.Role.SHOP_OWNER

    return render(
        request,
        "shops/dashboard.html",
        {
            **stats,
            "has_active_subscription": has_active_subscription,
            "subscription_status": subscription_status,
            "is_shop_owner": is_shop_owner,
        },
    )
