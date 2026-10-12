from django.db.models import F

from products.models import Product, ProductVariant

from .models import Shop, Subscription


def is_catalog_public(shop: Shop) -> bool:
    return shop.subscriptions.filter(
        status=Subscription.Status.ACTIVE
    ).exists()


def get_latest_subscription(shop: Shop) -> Subscription | None:
    """Return the shop's most recent Subscription row, or None.

    Ordered by starts_on descending, then id descending — the same
    "most recent first" ordering used by the admin subscription_list
    view.  Callers that need the actual row (e.g. an admin edit form)
    use this directly; callers that only need a status string use
    subscription_status().
    """
    return shop.subscriptions.order_by("-starts_on", "-id").first()


def subscription_status(shop: Shop) -> str:
    """Return the shop's latest subscription status, or "NONE".

    Possible return values: "NONE", "ACTIVE", "EXPIRED", "CANCELLED".
    "NONE" means the shop has never had a Subscription row.
    """
    latest = get_latest_subscription(shop)
    return latest.status if latest else "NONE"


def get_dashboard_stats(shop: Shop) -> dict:
    """Real product/variant/low-stock counts for a shop's dashboard.

    Scoped to active products only, so an archived product doesn't
    permanently inflate the merchant's own "Total products" count.
    """
    variants = ProductVariant.objects.filter(
        product__shop=shop,
        product__is_active=True,
    )

    return {
        "total_products": Product.objects.filter(
            shop=shop, is_active=True
        ).count(),
        "total_variants": variants.count(),
        "low_stock_count": variants.filter(
            stock_quantity__lte=F("low_stock_threshold")
        ).count(),
    }
