import re

from django.db import migrations


def _normalize_legacy_phone(value):
    """Normalize a stored phone using the SCRUM-66 input rules."""
    phone = re.sub(r"[\s()+\-]", "", str(value or ""))

    if not phone:
        raise ValueError("Phone number is empty.")

    if not phone.isascii() or not phone.isdigit():
        raise ValueError("Phone number contains invalid characters.")

    if phone.startswith("00"):
        phone = phone[2:]

    if phone.startswith("0"):
        phone = f"961{phone[1:]}"
    elif len(phone) in (7, 8):
        phone = f"961{phone}"

    if phone.startswith("961"):
        if not 10 <= len(phone) <= 11:
            raise ValueError(
                "Lebanese numbers must contain 10–11 digits including 961."
            )
    elif not 10 <= len(phone) <= 15:
        raise ValueError("Phone numbers must contain 10–15 digits.")

    return phone


def normalize_existing_customer_phones(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Customer = apps.get_model("customers", "Customer")
    Order = apps.get_model("orders", "Order")

    customers = list(
        Customer.objects.using(db_alias).order_by("shop_id", "pk")
    )

    # Validate and group every record before modifying any records.
    groups = {}

    for customer in customers:
        try:
            normalized_phone = _normalize_legacy_phone(
                customer.phone_number
            )
        except ValueError as exc:
            raise RuntimeError(
                f"Cannot normalize Customer pk={customer.pk}, "
                f"phone={customer.phone_number!r}: {exc}"
            ) from exc

        key = (customer.shop_id, normalized_phone)
        groups.setdefault(key, []).append(customer)

    for (shop_id, normalized_phone), records in groups.items():
        # Records are ordered by primary key; preserve the oldest record.
        keeper = records[0]

        for duplicate in records[1:]:
            # Preserve order history before deleting the duplicate customer.
            Order.objects.using(db_alias).filter(
                customer_id=duplicate.pk,
                shop_id=shop_id,
            ).update(customer_id=keeper.pk)

            Customer.objects.using(db_alias).filter(
                pk=duplicate.pk,
            ).delete()

        Customer.objects.using(db_alias).filter(
            pk=keeper.pk,
        ).update(phone_number=normalized_phone)


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0001_initial"),
        ("orders", "0002_alter_orderitem_variant"),
    ]

    operations = [
        migrations.RunPython(normalize_existing_customer_phones),
    ]
