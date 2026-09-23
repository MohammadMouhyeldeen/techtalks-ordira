from .models import Shop, Subscription


def is_catalog_public(shop: Shop) -> bool:
    return shop.subscriptions.filter(
        status=Subscription.Status.ACTIVE
    ).exists()