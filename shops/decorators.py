from functools import wraps

from django.shortcuts import render

from .helpers import is_catalog_public
from .models import Shop


def public_shop_required(view_func):
    """
    Resolves the `shop_slug` URL kwarg into a Shop before calling the view.

    - No Shop matches the slug: renders the shared "unavailable" template
      with state="shop_not_found" and a 404 status, instead of raising
      Http404 (there is no project-wide 404.html, so this keeps the result
      branded and consistent in both DEBUG and production).
    - Shop exists but has no active subscription: renders the same template
      with state="unavailable" and a 200 status (a paused shop is a
      legitimate, bookmarkable page, not an error).
    - Otherwise calls the view with `shop` passed in place of `shop_slug`.
    """
    @wraps(view_func)
    def _wrapped(request, shop_slug, *args, **kwargs):
        shop = Shop.objects.filter(slug=shop_slug).first()

        if shop is None:
            return render(
                request,
                "storefront/unavailable.html",
                {"state": "shop_not_found"},
                status=404,
            )

        if not is_catalog_public(shop):
            return render(
                request,
                "storefront/unavailable.html",
                {"state": "unavailable", "shop": shop},
                status=200,
            )

        return view_func(request, *args, shop=shop, **kwargs)

    return _wrapped
