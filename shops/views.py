from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import ShopSetupForm


@login_required
def dashboard(request):
    return render(request, "shops/dashboard.html")


@login_required
def shop_setup(request):
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
