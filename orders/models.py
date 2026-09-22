import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class Order(models.Model):
    class FulfillmentType(models.TextChoices):
        DELIVERY = "DELIVERY", "Delivery"
        PICKUP = "PICKUP", "Pickup"

    class Status(models.TextChoices):
        NEW = "NEW", "New Order"
        PREPARING = "PREPARING", "Preparing"
        HANDED_TO_DELIVERY = "HANDED_TO_DELIVERY", "Handed to Delivery"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    class Currency(models.TextChoices):
        USD = "USD", "USD"
        LBP = "LBP", "LBP"

    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.PROTECT,
        related_name="orders",
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="orders",
    )
    delivery_zone = models.ForeignKey(
        "shops.DeliveryZone",
        on_delete=models.SET_NULL,
        related_name="orders",
        blank=True,
        null=True,
    )
    selected_payment_method = models.ForeignKey(
        "shops.ShopPaymentMethod",
        on_delete=models.PROTECT,
        related_name="orders",
    )

    order_number = models.CharField(max_length=30, unique=True)
    tracking_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    fulfillment_type = models.CharField(
        max_length=20,
        choices=FulfillmentType.choices,
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.NEW,
    )

    customer_name_snapshot = models.CharField(max_length=150)
    customer_phone_snapshot = models.CharField(max_length=30)
    zone_name_snapshot = models.CharField(
        max_length=100,
        blank=True,
    )
    delivery_fee_snapshot = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    address_snapshot = models.TextField(blank=True)

    items_total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
    )
    fx_rate_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    cancellation_reason = models.TextField(blank=True)
    stock_restored_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        errors = {}

        if self.customer_id and self.customer.shop_id != self.shop_id:
            errors["customer"] = "Customer must belong to the selected shop."

        if (
            self.selected_payment_method_id
            and self.selected_payment_method.shop_id != self.shop_id
        ):
            errors["selected_payment_method"] = (
                "Payment method must belong to the selected shop."
            )

        if self.fulfillment_type == self.FulfillmentType.PICKUP:
            if self.delivery_zone_id:
                errors["delivery_zone"] = (
                    "Pickup orders cannot have a delivery zone."
                )
            if self.delivery_fee_snapshot != Decimal("0.00"):
                errors["delivery_fee_snapshot"] = (
                    "Pickup orders must have a zero delivery fee."
                )

        if self.fulfillment_type == self.FulfillmentType.DELIVERY:
            if not self.delivery_zone_id:
                errors["delivery_zone"] = (
                    "Delivery orders require a delivery zone."
                )
            elif self.delivery_zone.shop_id != self.shop_id:
                errors["delivery_zone"] = (
                    "Delivery zone must belong to the selected shop."
                )

            if not self.address_snapshot:
                errors["address_snapshot"] = (
                    "Delivery orders require an address."
                )

        if self.status == self.Status.CANCELLED and not self.cancellation_reason:
            errors["cancellation_reason"] = (
                "Cancelled orders require a cancellation reason."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    variant = models.ForeignKey(
        "products.ProductVariant",
        on_delete=models.PROTECT,
        related_name="order_items",
    )

    product_name_snapshot = models.CharField(max_length=150)
    size_snapshot = models.CharField(max_length=30)
    color_snapshot = models.CharField(max_length=50)
    unit_price_snapshot = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )
    line_total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    def clean(self):
        if (
            self.order_id
            and self.variant_id
            and self.variant.product.shop_id != self.order.shop_id
        ):
            raise ValidationError(
                {
                    "variant": (
                        "Product variant must belong to the order's shop."
                    ),
                }
            )

    def __str__(self):
        return f"{self.order.order_number} - {self.product_name_snapshot}"