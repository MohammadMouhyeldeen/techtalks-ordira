from .models import Notification


def notify_low_stock_if_crossed(*, variant, previous_quantity):
    current_quantity = variant.stock_quantity
    threshold = variant.low_stock_threshold

    crossed_threshold = (
        previous_quantity > threshold
        and current_quantity <= threshold
    )

    if not crossed_threshold:
        return None

    shop = variant.product.shop

    return Notification.objects.create(
        shop=shop,
        recipient=shop.owner,
        notification_type=Notification.Type.LOW_STOCK,
        message=(
            f"Low stock: {variant.product.name} "
            f"({variant.color}, {variant.size}) has "
            f"{current_quantity} remaining."
        ),
    )
