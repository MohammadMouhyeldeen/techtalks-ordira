from django.db import models


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

    def __str__(self):
        return f"{self.full_name} - {self.phone_number}"