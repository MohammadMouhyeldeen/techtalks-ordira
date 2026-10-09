from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from customers.models import Customer
from shops.models import Shop, ShopPaymentMethod

from .models import Order, OrderItem


User = get_user_model()


class MerchantOrderViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="merchant@example.com",
            password="testpass123",
            full_name="Merchant Owner",
            role=User.Role.SHOP_OWNER,
            status=User.Status.ACTIVE,
        )

        self.other_owner = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            full_name="Other Owner",
            role=User.Role.SHOP_OWNER,
            status=User.Status.ACTIVE,
        )

        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="testpass123",
            full_name="Platform Admin",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
        )

        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Merchant Shop",
            slug="merchant-shop-orders",
            pickup_available=True,
            exchange_rate_lbp_per_usd=Decimal("90000.00"),
        )

        self.other_shop = Shop.objects.create(
            owner=self.other_owner,
            name="Other Shop",
            slug="other-shop-orders",
            pickup_available=True,
            exchange_rate_lbp_per_usd=Decimal("90000.00"),
        )

        self.customer = Customer.objects.create(
            shop=self.shop,
            full_name="Customer Record",
            phone_number="03111111",
        )

        self.other_customer = Customer.objects.create(
            shop=self.other_shop,
            full_name="Other Customer",
            phone_number="03222222",
        )

        self.payment_method = ShopPaymentMethod.objects.create(
            shop=self.shop,
            method_name=ShopPaymentMethod.MethodName.CASH,
            enabled=True,
        )

        self.other_payment_method = ShopPaymentMethod.objects.create(
            shop=self.other_shop,
            method_name=ShopPaymentMethod.MethodName.CASH,
            enabled=True,
        )

        self.old_order = self.create_order(
            order_number="ORD-OLD",
            status=Order.Status.PREPARING,
            customer_name="Older Customer",
        )

        self.new_order = self.create_order(
            order_number="ORD-NEW",
            status=Order.Status.NEW,
            customer_name="Newest Customer",
        )

        self.other_order = self.create_order(
            shop=self.other_shop,
            customer=self.other_customer,
            payment_method=self.other_payment_method,
            order_number="ORD-OTHER",
            customer_name="Hidden Customer",
        )

        now = timezone.now()

        Order.objects.filter(pk=self.old_order.pk).update(
            created_at=now - timedelta(days=1),
        )
        Order.objects.filter(pk=self.new_order.pk).update(
            created_at=now,
        )

        OrderItem.objects.create(
            order=self.new_order,
            variant=None,
            product_name_snapshot="Classic T-shirt",
            color_snapshot="Black",
            size_snapshot="Medium",
            unit_price_snapshot=Decimal("10.00"),
            quantity=2,
            line_total=Decimal("20.00"),
        )

        self.list_url = reverse(
            "orders:order-list",
            kwargs={"shop_pk": self.shop.pk},
        )

    def create_order(
        self,
        *,
        order_number,
        customer_name,
        status=Order.Status.NEW,
        shop=None,
        customer=None,
        payment_method=None,
    ):
        shop = shop or self.shop
        customer = customer or self.customer
        payment_method = payment_method or self.payment_method

        return Order.objects.create(
            shop=shop,
            customer=customer,
            selected_payment_method=payment_method,
            order_number=order_number,
            fulfillment_type=Order.FulfillmentType.PICKUP,
            status=status,
            customer_name_snapshot=customer_name,
            customer_phone_snapshot=customer.phone_number,
            zone_name_snapshot="",
            delivery_fee_snapshot=Decimal("0.00"),
            address_snapshot="",
            items_total=Decimal("20.00"),
            total=Decimal("20.00"),
            currency=Order.Currency.USD,
            fx_rate_snapshot=Decimal("90000.00"),
        )

    def detail_url(self, order):
        return reverse(
            "orders:order-detail",
            kwargs={
                "shop_pk": self.shop.pk,
                "order_pk": order.pk,
            },
        )

    def test_order_list_shows_only_owner_shop_orders_newest_first(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)

        orders = list(response.context["orders"])

        self.assertEqual(
            [order.pk for order in orders],
            [self.new_order.pk, self.old_order.pk],
        )

        self.assertContains(response, "ORD-NEW")
        self.assertContains(response, "ORD-OLD")
        self.assertNotContains(response, "ORD-OTHER")
        self.assertNotContains(response, "Hidden Customer")

    def test_order_list_filters_by_status(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.list_url,
            {"status": Order.Status.PREPARING},
        )

        self.assertEqual(response.status_code, 200)

        orders = list(response.context["orders"])

        self.assertEqual(
            [order.pk for order in orders],
            [self.old_order.pk],
        )

        self.assertContains(response, "ORD-OLD")
        self.assertNotContains(response, "ORD-NEW")

    def test_invalid_status_filter_is_ignored(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.list_url,
            {"status": "INVALID"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_status"], "")
        self.assertEqual(len(response.context["orders"]), 2)

    def test_empty_shop_displays_empty_state(self):
        empty_shop = Shop.objects.create(
            owner=self.owner,
            name="Empty Shop",
            slug="empty-shop-orders",
            pickup_available=True,
            exchange_rate_lbp_per_usd=Decimal("90000.00"),
        )

        self.client.force_login(self.owner)

        response = self.client.get(
            reverse(
                "orders:order-list",
                kwargs={"shop_pk": empty_shop.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No orders found")

    def test_order_detail_displays_snapshot_values(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.detail_url(self.new_order)
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ORD-NEW")
        self.assertContains(response, "Newest Customer")
        self.assertContains(response, self.customer.phone_number)
        self.assertContains(response, "Pickup")
        self.assertContains(response, "Cash")
        self.assertContains(response, "Classic T-shirt")
        self.assertContains(response, "Black")
        self.assertContains(response, "Medium")
        self.assertContains(response, "20.00")
        self.assertContains(response, "USD")

    def test_order_detail_shows_not_available_when_payment_method_missing(self):
        # selected_payment_method is PROTECT + NOT NULL, so a shop can never
        # actually delete one out from under a real order — this mutates an
        # in-memory (unsaved) copy to exercise the template guard directly.
        order = self.new_order
        order.selected_payment_method = None

        html = render_to_string(
            "orders/order_detail.html",
            {"shop": self.shop, "order": order},
        )

        self.assertIn("Not available", html)

    def test_opening_other_shop_order_returns_404(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse(
                "orders:order-detail",
                kwargs={
                    "shop_pk": self.other_shop.pk,
                    "order_pk": self.other_order.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_anonymous_user_is_redirected_to_login(self):
        list_response = self.client.get(self.list_url)
        detail_response = self.client.get(
            self.detail_url(self.new_order)
        )

        self.assertEqual(list_response.status_code, 302)
        self.assertEqual(detail_response.status_code, 302)
        self.assertIn(
            reverse("accounts:login"),
            list_response.url,
        )
        self.assertIn(
            reverse("accounts:login"),
            detail_response.url,
        )

    def test_admin_cannot_access_merchant_order_pages(self):
        self.client.force_login(self.admin)

        list_response = self.client.get(self.list_url)
        detail_response = self.client.get(
            self.detail_url(self.new_order)
        )

        self.assertEqual(list_response.status_code, 404)
        self.assertEqual(detail_response.status_code, 404)

    def test_sidebar_contains_order_list_link_for_owner(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.list_url)
        self.assertContains(response, "<span>Orders</span>", html=True,)
