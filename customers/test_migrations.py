from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace

from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase

from accounts.models import User
from customers.models import Customer
from orders.models import Order
from shops.models import Shop, ShopPaymentMethod


class NormalizeExistingCustomerPhonesMigrationTests(TestCase):
    def setUp(self):
        super().setUp()

        migration_module = import_module(
            "customers.migrations.0002_normalize_existing_customer_phones"
        )

        self.normalize_existing_customer_phones = (
            migration_module.normalize_existing_customer_phones
        )

        self.historical_apps = MigrationLoader(
            connection
        ).project_state(
            [("customers", "0002_normalize_existing_customer_phones")]
        ).apps

        self.owner = User.objects.create_user(
            "migration-owner@example.com",
            "testpassword123",
            full_name="Migration Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )

        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Migration Shop",
            slug="migration-phone-shop",
            pickup_available=True,
            exchange_rate_lbp_per_usd=Decimal("89500.00"),
        )

        self.payment_method = ShopPaymentMethod.objects.create(
            shop=self.shop,
            method_name=ShopPaymentMethod.MethodName.CASH,
            enabled=True,
        )

        # Use bulk_create to simulate legacy records that predate
        # phone normalization and may contain duplicate phone formats.
        self.keeper, self.duplicate = Customer.objects.bulk_create(
            [
                Customer(
                    shop=self.shop,
                    full_name="Original Customer",
                    phone_number="+961 70 123 456",
                ),
                Customer(
                    shop=self.shop,
                    full_name="Duplicate Customer",
                    phone_number="070-123-456",
                ),
            ]
        )

        self.order = Order.objects.create(
            shop=self.shop,
            customer=self.duplicate,
            selected_payment_method=self.payment_method,
            order_number="MIGRATION-ORDER-1",
            fulfillment_type=Order.FulfillmentType.PICKUP,
            customer_name_snapshot="Duplicate Customer",
            customer_phone_snapshot="070-123-456",
            items_total=Decimal("10.00"),
            total=Decimal("10.00"),
            currency=Order.Currency.USD,
            fx_rate_snapshot=Decimal("89500.00"),
        )

    def test_migration_merges_duplicate_customers_and_preserves_orders(self):
        # Run the real migration function against the historical models.
        self.normalize_existing_customer_phones(
            self.historical_apps,
            SimpleNamespace(connection=connection),
        )

        self.keeper.refresh_from_db()
        self.order.refresh_from_db()

        # The customer with the lowest primary key survives.
        self.assertEqual(self.keeper.phone_number, "96170123456")

        # The redundant customer record is removed.
        self.assertFalse(
            Customer.objects.filter(pk=self.duplicate.pk).exists()
        )

        # The existing order now belongs to the canonical customer.
        self.assertEqual(self.order.customer_id, self.keeper.pk)

        # There is only one customer with this canonical number in the shop.
        self.assertEqual(
            Customer.objects.filter(
                shop=self.shop,
                phone_number="96170123456",
            ).count(),
            1,
        )

        # Historical order snapshots are intentionally left unchanged.
        self.assertEqual(
            self.order.customer_phone_snapshot,
            "070-123-456",
        )
        self.assertEqual(
            self.order.customer_name_snapshot,
            "Duplicate Customer",
        )
