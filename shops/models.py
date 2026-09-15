from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from decimal import Decimal

class Shop(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="shops",
    )
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, unique=True)
    whatsapp = models.CharField(max_length=30, blank=True)
    instagram = models.CharField(max_length=100, blank=True)
    logo = models.ImageField(
        upload_to="shop_logos/",
        blank=True,
        null=True,
    )
    pickup_available = models.BooleanField(default=False)
    exchange_rate_lbp_per_usd = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Subscription(models.Model):
    class Plan(models.TextChoices):
        FREE = "FREE", "Free"
        BASIC = "BASIC", "Basic"
        PREMIUM = "PREMIUM", "Premium"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        EXPIRED = "EXPIRED", "Expired"
        CANCELLED = "CANCELLED", "Cancelled"

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    plan = models.CharField(
        max_length=20,
        choices=Plan.choices,
        default=Plan.FREE,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    starts_on = models.DateField()
    ends_on = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"{self.shop.name} - {self.plan}"


class DeliveryZone(models.Model):
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="delivery_zones",
    )
    area_name = models.CharField(max_length=100)
    fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["shop", "area_name"],
                name="unique_delivery_zone_per_shop",
            ),
        ]
        ordering = ["area_name"]

    def __str__(self):
        return f"{self.shop.name} - {self.area_name}"



  