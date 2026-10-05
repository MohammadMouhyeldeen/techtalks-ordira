import secrets
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from customers.models import Customer
from products.models import ProductVariant, StockMovement

from .models import Order, OrderItem


MONEY_PLACES = Decimal("0.01")


def _round_money(value):
    return value.quantize(
        MONEY_PLACES,
        rounding=ROUND_HALF_UP,
    )


def _convert_currency(*, amount, from_currency, to_currency, fx_rate):
    amount = Decimal(amount)
    fx_rate = Decimal(fx_rate)

    if from_currency == to_currency:
        return _round_money(amount)

    if from_currency == Order.Currency.USD and to_currency == Order.Currency.LBP:
        return _round_money(amount * fx_rate)

    if from_currency == Order.Currency.LBP and to_currency == Order.Currency.USD:
        return _round_money(amount / fx_rate)

    raise ValidationError("Unsupported currency conversion.")


def _generate_order_number():
    for _ in range(5):
        order_number = f"ORD-{secrets.token_hex(12).upper()}"

        if not Order.objects.filter(order_number=order_number).exists():
            return order_number

    raise RuntimeError("Could not generate a unique order number.")


def _normalize_items(items):
    if not items:
        raise ValidationError("The order must contain at least one item.")

    requested_quantities = defaultdict(int)

    for item in items:
        if not isinstance(item, dict):
            raise ValidationError("Each order item must be valid.")

        variant_id = item.get("variant_id")
        quantity = item.get("quantity")

        if isinstance(variant_id, bool):
            raise ValidationError("Every order item requires a valid variant.")

        try:
            variant_id_decimal = Decimal(str(variant_id))
        except (TypeError, ValueError, ArithmeticError):
            raise ValidationError(
                "Every order item requires a valid variant."
            )

        if (
            variant_id_decimal <= 0
            or variant_id_decimal
            != variant_id_decimal.to_integral_value()
        ):
            raise ValidationError(
                "Every order item requires a valid variant."
            )

        if isinstance(quantity, bool):
            raise ValidationError(
                "Item quantity must be a positive integer."
            )

        try:
            quantity_decimal = Decimal(str(quantity))
        except (TypeError, ValueError, ArithmeticError):
            raise ValidationError(
                "Item quantity must be a positive integer."
            )

        if (
            quantity_decimal <= 0
            or quantity_decimal
            != quantity_decimal.to_integral_value()
        ):
            raise ValidationError(
                "Item quantity must be a positive integer."
            )

        requested_quantities[int(variant_id_decimal)] += int(
            quantity_decimal
        )

    return requested_quantities

@transaction.atomic
def create_order(
    *,
    shop,
    customer_name,
    customer_phone,
    fulfillment_type,
    selected_payment_method,
    items,
    currency,
    delivery_zone=None,
    address="",
):
    customer_name = customer_name.strip()
    customer_phone = customer_phone.strip()
    address = address.strip()

    if not customer_name:
        raise ValidationError("Customer name is required.")

    if not customer_phone:
        raise ValidationError("Customer phone number is required.")

    if currency not in Order.Currency.values:
        raise ValidationError("Unsupported order currency.")

    if fulfillment_type not in Order.FulfillmentType.values:
        raise ValidationError("Unsupported fulfillment type.")

    if (
        selected_payment_method.shop_id != shop.pk
        or not selected_payment_method.enabled
    ):
        raise ValidationError(
            "The selected payment method is not available for this shop."
        )

    if fulfillment_type == Order.FulfillmentType.DELIVERY:
        if delivery_zone is None:
            raise ValidationError("A delivery zone is required.")

        if delivery_zone.shop_id != shop.pk or not delivery_zone.is_active:
            raise ValidationError(
                "The selected delivery zone is not available."
            )

        if not address:
            raise ValidationError("A delivery address is required.")

    else:
        if not shop.pickup_available:
            raise ValidationError("Pickup is not available for this shop.")

        if delivery_zone is not None:
            raise ValidationError(
                "Pickup orders cannot have a delivery zone."
            )

        address = ""

    requested_quantities = _normalize_items(items)

    locked_variants = {
        variant.pk: variant
        for variant in (
            ProductVariant.objects
            .select_for_update(of=("self",))
            .select_related("product")
            .filter(pk__in=requested_quantities)
            .order_by("pk")
        )
    }

    if len(locked_variants) != len(requested_quantities):
        raise ValidationError(
            "One or more selected product variants do not exist."
        )

    fx_rate = Decimal(shop.exchange_rate_lbp_per_usd)
    prepared_items = []
    items_total = Decimal("0.00")

    for variant_id, quantity in requested_quantities.items():
        variant = locked_variants[variant_id]

        if variant.product.shop_id != shop.pk:
            raise ValidationError(
                "All product variants must belong to the selected shop."
            )

        if not variant.product.is_active or not variant.is_active:
            raise ValidationError(
                f"{variant.product.name} is no longer available."
            )

        if variant.stock_quantity < quantity:
            raise ValidationError(
                f"Not enough stock is available for {variant}."
            )

        unit_price = _convert_currency(
            amount=variant.unit_price,
            from_currency=variant.currency,
            to_currency=currency,
            fx_rate=fx_rate,
        )
        line_total = _round_money(unit_price * quantity)
        items_total += line_total

        prepared_items.append(
            {
                "variant": variant,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": line_total,
            }
        )

    items_total = _round_money(items_total)

    if fulfillment_type == Order.FulfillmentType.DELIVERY:
        delivery_fee = _convert_currency(
            amount=delivery_zone.fee,
            from_currency=Order.Currency.USD,
            to_currency=currency,
            fx_rate=fx_rate,
        )
        zone_name = delivery_zone.area_name
    else:
        delivery_fee = Decimal("0.00")
        zone_name = ""

    total = _round_money(items_total + delivery_fee)

    customer, _ = Customer.objects.get_or_create(
        shop=shop,
        phone_number=customer_phone,
        defaults={"full_name": customer_name},
    )

    order = Order(
        shop=shop,
        customer=customer,
        delivery_zone=delivery_zone,
        selected_payment_method=selected_payment_method,
        order_number=_generate_order_number(),
        fulfillment_type=fulfillment_type,
        customer_name_snapshot=customer_name,
        customer_phone_snapshot=customer_phone,
        zone_name_snapshot=zone_name,
        delivery_fee_snapshot=delivery_fee,
        address_snapshot=address,
        items_total=items_total,
        total=total,
        currency=currency,
        fx_rate_snapshot=fx_rate,
    )
    order.full_clean()
    order.save()

    for prepared_item in prepared_items:
        variant = prepared_item["variant"]
        quantity = prepared_item["quantity"]

        OrderItem.objects.create(
            order=order,
            variant=variant,
            product_name_snapshot=variant.product.name,
            size_snapshot=variant.size,
            color_snapshot=variant.color,
            unit_price_snapshot=prepared_item["unit_price"],
            quantity=quantity,
            line_total=prepared_item["line_total"],
        )

        variant.stock_quantity -= quantity
        variant.save(update_fields=["stock_quantity"])

        StockMovement.objects.create(
            variant=variant,
            created_by=None,
            change_qty=-quantity,
            reason=StockMovement.Reason.SALE,
        )

    return order


@transaction.atomic
def cancel_order(order, reason):
    locked_order = (
        Order.objects
        .select_for_update()
        .get(pk=order.pk)
    )

    if locked_order.status == Order.Status.CANCELLED:
        return locked_order

    if locked_order.status == Order.Status.COMPLETED:
        raise ValidationError(
            "Completed orders cannot be cancelled."
        )

    reason = str(reason or "").strip()

    if not reason:
        raise ValidationError(
            "A cancellation reason is required."
        )

    order_items = list(
        locked_order.items
        .all()
        .order_by("pk")
    )

    variant_ids = sorted(
        {
            item.variant_id
            for item in order_items
            if item.variant_id is not None
        }
    )

    locked_variants = {
        variant.pk: variant
        for variant in (
            ProductVariant.objects
            .select_for_update(of=("self",))
            .filter(pk__in=variant_ids)
            .order_by("pk")
        )
    }

    for item in order_items:
        variant = locked_variants.get(item.variant_id)

        if variant is None:
            continue

        variant.stock_quantity += item.quantity
        variant.save(update_fields=["stock_quantity"])

        StockMovement.objects.create(
            variant=variant,
            created_by=None,
            change_qty=item.quantity,
            reason=StockMovement.Reason.CANCELLATION,
        )

    locked_order.status = Order.Status.CANCELLED
    locked_order.cancellation_reason = reason
    locked_order.stock_restored_at = timezone.now()
    locked_order.full_clean()
    locked_order.save(
        update_fields=[
            "status",
            "cancellation_reason",
            "stock_restored_at",
        ]
    )

    return locked_order