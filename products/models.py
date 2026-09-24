from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

class Category(models.Model):
    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.CASCADE,
        related_name="categories",
    )
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["shop", "name"],
                name="unique_category_name_per_shop",
            ),
        ]

    def __str__(self):
        return f"{self.shop.name} - {self.name}"


class Product(models.Model):
    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.CASCADE,
        related_name="products",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    image = models.ImageField(
        upload_to="product_images/",
        blank=True,
        null=True,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def clean(self):
        super().clean()

        if (
            self.shop_id
            and self.category_id
            and self.category.shop_id != self.shop_id
        ):
            raise ValidationError(
                {
                    "category": (
                        "The selected category must belong to the same shop."
                    )
                }
            )

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    class Currency(models.TextChoices):
        USD = "USD", "USD"
        LBP = "LBP", "LBP"

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
    )
    color = models.CharField(max_length=50)
    size = models.CharField(max_length=30)
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.USD,
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "color", "size"],
                name="unique_variant_per_product",
            ),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.color} - {self.size}"


class StockMovement(models.Model):
    class Reason(models.TextChoices):
        SALE = "SALE", "Sale"
        RESTOCK = "RESTOCK", "Restock"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"
        CANCELLATION = "CANCELLATION", "Cancellation"
        DAMAGE = "DAMAGE", "Damage"

    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="recorded_stock_movements",
        blank=True,
        null=True,
    )
    change_qty = models.IntegerField()
    reason = models.CharField(
        max_length=20,
        choices=Reason.choices,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.variant} | {self.change_qty} | {self.reason}"