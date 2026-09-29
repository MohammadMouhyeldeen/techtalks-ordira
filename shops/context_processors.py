def current_shop(request):
    """Makes the logged-in owner's shop available as `shop` in every
    template rendered through the merchant shell (base.html), without
    every view needing to remember to pass it explicitly."""
    if request.user.is_authenticated:
        shop = request.user.shops.first()
        if shop is not None:
            return {"shop": shop}

    return {}
