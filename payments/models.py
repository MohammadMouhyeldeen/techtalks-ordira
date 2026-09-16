from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class Payment(models.Model):
    class Currency(models.TextChoices):
        USD = "USD", "USD"
        LBP = "LBP", "LBP"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="payment",
    )
    method = models.ForeignKey(
        "shops.ShopPaymentMethod",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
    )
    amount_in_order_currency = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    method_name_snapshot = models.CharField(max_length=30)
    received_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    def clean(self):
        if (
            self.order_id
            and self.method_id
            and self.method.shop_id != self.order.shop_id
        ):
            raise ValidationError(
                {
                    "method": (
                        "Payment method must belong to the order's shop."
                    ),
                }
            )

    def __str__(self):
        return f"{self.order.order_number} - {self.status}"


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ISSUED = "ISSUED", "Issued"
        VOID = "VOID", "Void"

    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="invoice",
    )
    invoice_number = models.CharField(max_length=30, unique=True)
    issued_at = models.DateTimeField(blank=True, null=True)
    subtotal_snapshot = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    delivery_fee_snapshot = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    total_snapshot = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    currency = models.CharField(
        max_length=3,
        choices=Payment.Currency.choices,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    def clean(self):
        if self.order_id and self.shop_id != self.order.shop_id:
            raise ValidationError(
                {"shop": "Invoice and order must belong to the same shop."}
            )

    def __str__(self):
        return self.invoice_number