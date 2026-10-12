from django.db import migrations


def seed_cash_payment_method(apps, schema_editor):
    Shop = apps.get_model("shops", "Shop")
    ShopPaymentMethod = apps.get_model("shops", "ShopPaymentMethod")

    existing_shop_ids = set(
        ShopPaymentMethod.objects.values_list("shop_id", flat=True).distinct()
    )

    shops_without_payment_methods = Shop.objects.exclude(
        pk__in=existing_shop_ids
    )

    ShopPaymentMethod.objects.bulk_create(
        [
            ShopPaymentMethod(
                shop=shop,
                method_name="CASH",
                enabled=True,
            )
            for shop in shops_without_payment_methods
        ],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("shops", "0002_subscription_one_active_per_shop"),
    ]

    operations = [
        migrations.RunPython(
            seed_cash_payment_method,
            migrations.RunPython.noop,
        ),
    ]
