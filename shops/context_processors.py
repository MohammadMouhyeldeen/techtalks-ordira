def current_shop(request):
    """Makes the logged-in owner's shop available as `shop` in every
    template rendered through the merchant shell (base.html), without
    every view needing to remember to pass it explicitly."""
    if request.user.is_authenticated:
        shop = request.user.shops.first()
        if shop is not None:
            return {"shop": shop}

    return {}


def storefront_cart(request):
    """Makes the guest's cart count available as `cart_count` on every
    storefront page, for the navbar badge. public_shop_required stashes
    request.public_shop on success so this needs no extra Shop query in
    the common case."""
    shop = getattr(request, "public_shop", None)

    if shop is None:
        shop_slug = getattr(request, "resolver_match", None) and (
            request.resolver_match.kwargs.get("shop_slug")
        )
        if not shop_slug:
            return {}

        from .models import Shop

        shop = Shop.objects.filter(slug=shop_slug).first()
        if shop is None:
            return {}

    from products import cart

    return {"cart_count": cart.get_item_count(request, shop)}
