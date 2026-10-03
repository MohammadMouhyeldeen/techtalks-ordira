import re

from django.core.exceptions import ValidationError
from django.db import models


def normalize_phone_number(value: str) -> str:
    """Normalize and validate a Customer phone number."""

    phone = (value or "").strip()

    if not phone:
        raise ValidationError(
            "Phone number is required."
        )

    if phone.startswith("+"):
        phone = phone[1:]

    phone = re.sub(r"[\s\-\(\)\[\]]", "", phone)

    if (
        not phone.isdigit()
        or not phone.isascii()
        or not 10 <= len(phone) <= 15
    ):
        raise ValidationError(
            "Enter a phone number with 10 to 15 digits, "
            "including the country code."
        )

    if phone.startswith("0"):
        raise ValidationError(
            "Enter the phone number with the country code."
        )

    return phone

class Customer(models.Model):
    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.CASCADE,
        related_name="customers",
    )
    full_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=30)

    class Meta:
        ordering = ["full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["shop", "phone_number"],
                name="unique_customer_phone_per_shop",
            ),
        ]

    def save(self, *args, **kwargs):
        self.phone_number = normalize_phone_number(self.phone_number)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} - {self.phone_number}"
