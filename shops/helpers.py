from django.db.models import F

from products.models import Product, ProductVariant

from .models import Shop, Subscription


def is_catalog_public(shop: Shop) -> bool:
    return shop.subscriptions.filter(
        status=Subscription.Status.ACTIVE
    ).exists()


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
