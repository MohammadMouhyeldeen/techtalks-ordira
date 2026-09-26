from django.core.exceptions import ValidationError
from django.db import transaction

from .models import ProductVariant, StockMovement


@transaction.atomic
def adjust_variant_stock(*, variant, change_qty, reason, created_by):
    locked_variant = (
        ProductVariant.objects
        .select_for_update()
        .get(pk=variant.pk)
    )

    if not locked_variant.is_active:
        raise ValidationError(
            "Archived product variants cannot be adjusted."
        )

    if change_qty == 0:
        raise ValidationError(
            "Stock adjustment quantity cannot be zero."
        )

    if reason not in StockMovement.Reason.values:
        raise ValidationError(
            "Invalid stock movement reason."
        )

    new_quantity = locked_variant.stock_quantity + change_qty

    if new_quantity < 0:
        raise ValidationError(
            "This adjustment would make the stock quantity negative."
        )

    locked_variant.stock_quantity = new_quantity
    locked_variant.save(update_fields=["stock_quantity"])

    movement = StockMovement.objects.create(
        variant=locked_variant,
        created_by=created_by,
        change_qty=change_qty,
        reason=reason,
    )

    return movement