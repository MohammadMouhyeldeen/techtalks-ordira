from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from orders.models import Order

from .models import Payment


MONEY_PLACES = Decimal("0.01")


def _round_money(value):
    return Decimal(value).quantize(
        MONEY_PLACES,
        rounding=ROUND_HALF_UP,
    )


def _convert_to_order_currency(*, amount, currency, order):
    amount = Decimal(amount)
    fx_rate = Decimal(order.fx_rate_snapshot)

    if currency == order.currency:
        return _round_money(amount)

    if (
        currency == Payment.Currency.USD
        and order.currency == Order.Currency.LBP
    ):
        return _round_money(amount * fx_rate)

    if (
        currency == Payment.Currency.LBP
        and order.currency == Order.Currency.USD
    ):
        return _round_money(amount / fx_rate)

    raise ValidationError("Unsupported payment currency conversion.")


@transaction.atomic
def record_payment(
    *,
    order,
    method,
    amount,
    currency,
    note="",
):
    locked_order = (
        Order.objects
        .select_for_update()
        .get(pk=order.pk)
    )

    if locked_order.status == Order.Status.CANCELLED:
        raise ValidationError(
            "Cancelled orders cannot receive payments."
        )

    if Payment.objects.filter(order=locked_order).exists():
        raise ValidationError(
            "A payment has already been recorded for this order."
        )

    if method.shop_id != locked_order.shop_id or not method.enabled:
        raise ValidationError(
            "The selected payment method is not available for this shop."
        )

    if currency not in Payment.Currency.values:
        raise ValidationError("Unsupported payment currency.")

    amount = _round_money(amount)

    if amount <= Decimal("0.00"):
        raise ValidationError(
            "Payment amount must be greater than zero."
        )

    amount_in_order_currency = _convert_to_order_currency(
        amount=amount,
        currency=currency,
        order=locked_order,
    )

    if amount_in_order_currency > locked_order.total:
        raise ValidationError(
            "Payment amount cannot exceed the order total."
        )

    payment = Payment(
        order=locked_order,
        method=method,
        amount=amount,
        currency=currency,
        amount_in_order_currency=amount_in_order_currency,
        method_name_snapshot=method.get_method_name_display(),
        received_at=timezone.now(),
        status=Payment.Status.PAID,
        note=note.strip(),
    )
    payment.full_clean()
    payment.save()

    return payment