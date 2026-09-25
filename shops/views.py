
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from accounts.models import User
from .forms import ShopSetupForm, ShopSettingsForm
from .helpers import get_dashboard_stats


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
        else {"total_products": 0, "total_variants": 0, "low_stock_count": 0}
    )

    return render(request, "shops/dashboard.html", stats)


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
