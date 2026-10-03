from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import User
from customers.models import Customer
from shops.models import Shop, ShopPaymentMethod

from .models import Order


class OrderCustomerIsolationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "order-owner@example.com",
            "testpassword123",
            full_name="Order Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )

        self.shop_a = Shop.objects.create(
            owner=self.owner,
            name="Shop A",
            slug="order-shop-a",
            exchange_rate_lbp_per_usd=89500,
        )

        self.shop_b = Shop.objects.create(
            owner=self.owner,
            name="Shop B",
            slug="order-shop-b",
            exchange_rate_lbp_per_usd=89500,
        )

        self.payment_method = ShopPaymentMethod.objects.create(
            shop=self.shop_a,
            method_name=ShopPaymentMethod.MethodName.CASH,
        )

        self.customer_from_shop_b = Customer.objects.create(
            shop=self.shop_b,
            full_name="Shop B Customer",
            phone_number="+961 70-123-(456)",
        )

    def test_order_rejects_customer_from_another_shop(self):
        order = Order(
            shop=self.shop_a,
            customer=self.customer_from_shop_b,
            selected_payment_method=self.payment_method,
            order_number="TEST-001",
            fulfillment_type=Order.FulfillmentType.PICKUP,
            customer_name_snapshot=self.customer_from_shop_b.full_name,
            customer_phone_snapshot=self.customer_from_shop_b.phone_number,
            items_total=Decimal("0.00"),
            total=Decimal("0.00"),
            currency=Order.Currency.USD,
            fx_rate_snapshot=Decimal("89500.00"),
        )

        with self.assertRaises(ValidationError) as context:
            order.full_clean()

        self.assertIn("customer", context.exception.message_dict)
        self.assertEqual(
            context.exception.message_dict["customer"][0],
            "Customer must belong to the selected shop.",
        )
