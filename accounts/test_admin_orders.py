from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from customers.models import Customer
from orders.models import Order, OrderItem
from products.models import Category, Product, ProductVariant
from shops.models import DeliveryZone, Shop, ShopPaymentMethod


class AdminOrderMonitoringTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="monitor-admin@example.com",
            password="GoodPassword99!",
            full_name="Monitoring Admin",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
        )

        self.owner_a = User.objects.create_user(
            email="monitor-owner-a@example.com",
            password="GoodPassword99!",
            full_name="Owner A",
            role=User.Role.SHOP_OWNER,
            status=User.Status.ACTIVE,
        )
        self.owner_b = User.objects.create_user(
            email="monitor-owner-b@example.com",
            password="GoodPassword99!",
            full_name="Owner B",
            role=User.Role.SHOP_OWNER,
            status=User.Status.ACTIVE,
        )

        self.shop_a = Shop.objects.create(
            owner=self.owner_a,
            name="Monitoring Shop A",
            slug="monitoring-shop-a",
            exchange_rate_lbp_per_usd=Decimal("89500.00"),
        )
        self.shop_b = Shop.objects.create(
            owner=self.owner_b,
            name="Monitoring Shop B",
            slug="monitoring-shop-b",
            exchange_rate_lbp_per_usd=Decimal("89500.00"),
        )

        self.customer_a = Customer.objects.create(
            shop=self.shop_a,
            full_name="Customer A",
            phone_number="70123456",
        )
        self.customer_b = Customer.objects.create(
            shop=self.shop_b,
            full_name="Customer B",
            phone_number="70999999",
        )

        self.payment_a = ShopPaymentMethod.objects.create(
            shop=self.shop_a,
            method_name=ShopPaymentMethod.MethodName.CASH,
            enabled=True,
        )
        self.payment_b = ShopPaymentMethod.objects.create(
            shop=self.shop_b,
            method_name=ShopPaymentMethod.MethodName.CASH,
            enabled=True,
        )

        self.url = reverse("accounts:admin_orders")

    def create_order(
        self,
        *,
        shop,
        customer,
        payment_method,
        order_number,
        status=Order.Status.NEW,
        delivery_zone=None,
    ):
        delivery_fee = (
            delivery_zone.fee
            if delivery_zone is not None
            else Decimal("0.00")
        )

        return Order.objects.create(
            shop=shop,
            customer=customer,
            delivery_zone=delivery_zone,
            selected_payment_method=payment_method,
            order_number=order_number,
            fulfillment_type=(
                Order.FulfillmentType.DELIVERY
                if delivery_zone is not None
                else Order.FulfillmentType.PICKUP
            ),
            status=status,
            customer_name_snapshot=customer.full_name,
            customer_phone_snapshot=customer.phone_number,
            zone_name_snapshot=(
                delivery_zone.area_name
                if delivery_zone is not None
                else ""
            ),
            delivery_fee_snapshot=delivery_fee,
            address_snapshot=(
                "Test delivery address"
                if delivery_zone is not None
                else ""
            ),
            items_total=Decimal("20.00"),
            total=Decimal("20.00") + delivery_fee,
            currency=Order.Currency.USD,
            fx_rate_snapshot=shop.exchange_rate_lbp_per_usd,
        )

    def test_admin_sees_orders_from_two_shops(self):
        order_a = self.create_order(
            shop=self.shop_a,
            customer=self.customer_a,
            payment_method=self.payment_a,
            order_number="MONITOR-A-001",
        )
        order_b = self.create_order(
            shop=self.shop_b,
            customer=self.customer_b,
            payment_method=self.payment_b,
            order_number="MONITOR-B-001",
        )

        self.client.force_login(self.admin)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {order.pk for order in response.context["orders"]},
            {order_a.pk, order_b.pk},
        )
        self.assertContains(response, "MONITOR-A-001")
        self.assertContains(response, "MONITOR-B-001")
        self.assertContains(response, "Monitoring Shop A")
        self.assertContains(response, "Monitoring Shop B")

    def test_filter_by_shop(self):
        order_a = self.create_order(
            shop=self.shop_a,
            customer=self.customer_a,
            payment_method=self.payment_a,
            order_number="FILTER-SHOP-A",
        )
        self.create_order(
            shop=self.shop_b,
            customer=self.customer_b,
            payment_method=self.payment_b,
            order_number="FILTER-SHOP-B",
        )

        self.client.force_login(self.admin)
        response = self.client.get(
            self.url,
            {"shop": str(self.shop_a.pk)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [order.pk for order in response.context["orders"]],
            [order_a.pk],
        )
        self.assertContains(response, "FILTER-SHOP-A")
        self.assertNotContains(response, "FILTER-SHOP-B")

    def test_filter_by_status(self):
        self.create_order(
            shop=self.shop_a,
            customer=self.customer_a,
            payment_method=self.payment_a,
            order_number="FILTER-NEW",
            status=Order.Status.NEW,
        )
        preparing_order = self.create_order(
            shop=self.shop_b,
            customer=self.customer_b,
            payment_method=self.payment_b,
            order_number="FILTER-PREPARING",
            status=Order.Status.PREPARING,
        )

        self.client.force_login(self.admin)
        response = self.client.get(
            self.url,
            {"status": Order.Status.PREPARING},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [order.pk for order in response.context["orders"]],
            [preparing_order.pk],
        )
        self.assertContains(response, "FILTER-PREPARING")
        self.assertNotContains(response, "FILTER-NEW")

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_shop_owner_is_redirected_away_from_admin_orders(self):
        self.client.force_login(self.owner_a)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("shops:dashboard"))

    def test_empty_state_when_there_are_no_orders(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No orders found")

    def test_deleted_variant_does_not_break_order_monitoring(self):
        order = self.create_order(
            shop=self.shop_a,
            customer=self.customer_a,
            payment_method=self.payment_a,
            order_number="DELETED-VARIANT-001",
        )

        category = Category.objects.create(
            shop=self.shop_a,
            name="Monitoring Clothing",
        )
        product = Product.objects.create(
            shop=self.shop_a,
            category=category,
            name="Snapshot Jacket",
        )
        variant = ProductVariant.objects.create(
            product=product,
            color="Blue",
            size="M",
            unit_price=Decimal("20.00"),
            stock_quantity=5,
        )

        item = OrderItem.objects.create(
            order=order,
            variant=variant,
            product_name_snapshot="Snapshot Jacket",
            color_snapshot="Blue",
            size_snapshot="M",
            unit_price_snapshot=Decimal("20.00"),
            quantity=1,
            line_total=Decimal("20.00"),
        )

        variant.delete()
        item.refresh_from_db()

        self.assertIsNone(item.variant)
        self.assertEqual(item.product_name_snapshot, "Snapshot Jacket")
        self.assertEqual(item.size_snapshot, "M")

        self.client.force_login(self.admin)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DELETED-VARIANT-001")

    def test_deleted_delivery_zone_does_not_break_order_monitoring(self):
        zone = DeliveryZone.objects.create(
            shop=self.shop_a,
            area_name="Monitoring Zone",
            fee=Decimal("5.00"),
        )
        order = self.create_order(
            shop=self.shop_a,
            customer=self.customer_a,
            payment_method=self.payment_a,
            order_number="DELETED-ZONE-001",
            delivery_zone=zone,
        )

        zone.delete()
        order.refresh_from_db()

        self.assertIsNone(order.delivery_zone)
        self.assertEqual(order.zone_name_snapshot, "Monitoring Zone")

        self.client.force_login(self.admin)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DELETED-ZONE-001")

    def test_only_latest_100_orders_are_returned(self):
        for index in range(101):
            self.create_order(
                shop=self.shop_a,
                customer=self.customer_a,
                payment_method=self.payment_a,
                order_number=f"MONITOR-LIMIT-{index:03d}",
            )

        self.client.force_login(self.admin)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        orders = list(response.context["orders"])
        order_numbers = {order.order_number for order in orders}

        self.assertEqual(len(orders), 100)
        self.assertIn("MONITOR-LIMIT-100", order_numbers)
        self.assertNotIn("MONITOR-LIMIT-000", order_numbers)

    def test_admin_dashboard_links_to_order_monitoring(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("accounts:admin_dashboard")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.url)
        self.assertContains(response, "Order Monitoring")

    def test_post_is_rejected_without_modifying_order(self):
        order = self.create_order(
            shop=self.shop_a,
            customer=self.customer_a,
            payment_method=self.payment_a,
            order_number="READ-ONLY-001",
            status=Order.Status.NEW,
        )

        self.client.force_login(self.admin)

        response = self.client.post(
            self.url,
            {
                "order_id": order.pk,
                "status": Order.Status.CANCELLED,
            },
        )

        self.assertEqual(response.status_code, 405)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.NEW)
