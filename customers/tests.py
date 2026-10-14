from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from orders.models import Order
from shops.models import Shop, ShopPaymentMethod

from .models import Customer


class CustomerModelTests(TestCase):
    def setUp(self):
        self.owner_a = User.objects.create_user(
            "customer-owner-a@example.com",
            "testpassword123",
            full_name="Customer Owner A",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )

        self.owner_b = User.objects.create_user(
            "customer-owner-b@example.com",
            "testpassword123",
            full_name="Customer Owner B",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )

        self.shop_a = Shop.objects.create(
            owner=self.owner_a,
            name="Shop A",
            slug="customer-shop-a",
            exchange_rate_lbp_per_usd=89500,
        )

        self.shop_b = Shop.objects.create(
            owner=self.owner_b,
            name="Shop B",
            slug="customer-shop-b",
            exchange_rate_lbp_per_usd=89500,
        )

    def test_customer_belongs_to_shop(self):
        customer = Customer.objects.create(
            shop=self.shop_a,
            full_name="Ahmad Ali",
            phone_number="+961 70-123-(456)",
        )

        self.assertEqual(customer.shop, self.shop_a)
        self.assertEqual(
            self.shop_a.customers.get(pk=customer.pk),
            customer,
        )

    def test_phone_number_is_normalized_on_save(self):
        customer = Customer.objects.create(
            shop=self.shop_a,
            full_name="Ahmad Ali",
            phone_number="+961 70-123-(456)",
        )

        self.assertEqual(
            customer.phone_number,
            "96170123456",
        )

    def test_same_normalized_phone_is_rejected_within_same_shop(self):
        Customer.objects.create(
            shop=self.shop_a,
            full_name="First Customer",
            phone_number="+961 70-123-(456)",
        )

        with self.assertRaises(IntegrityError):
            Customer.objects.create(
                shop=self.shop_a,
                full_name="Second Customer",
                phone_number="96170123456",
            )

    def test_same_normalized_phone_is_allowed_in_different_shops(self):
        customer_a = Customer.objects.create(
            shop=self.shop_a,
            full_name="Customer A",
            phone_number="+961 70-123-(456)",
        )

        customer_b = Customer.objects.create(
            shop=self.shop_b,
            full_name="Customer B",
            phone_number="96170123456",
        )

        self.assertEqual(
            customer_a.phone_number,
            customer_b.phone_number,
        )
        self.assertNotEqual(
            customer_a.shop_id,
            customer_b.shop_id,
        )

    def test_different_phone_numbers_are_allowed_within_same_shop(self):
        first = Customer.objects.create(
            shop=self.shop_a,
            full_name="First Customer",
            phone_number="+961 70-123-(456)",
        )

        second = Customer.objects.create(
            shop=self.shop_a,
            full_name="Second Customer",
            phone_number="+961 71-123-(456)",
        )

        self.assertNotEqual(
            first.phone_number,
            second.phone_number,
        )

    def test_invalid_phone_number_is_rejected(self):
        with self.assertRaises(ValidationError):
            Customer.objects.create(
                shop=self.shop_a,
                full_name="Invalid Customer",
                phone_number="hello world",
            )

    def test_customer_does_not_create_user_account(self):
        user_count_before = User.objects.count()

        Customer.objects.create(
            shop=self.shop_a,
            full_name="Guest Customer",
            phone_number="+961 70-123-(456)",
        )

        self.assertEqual(
            User.objects.count(),
            user_count_before,
        )

    def test_shop_customer_query_is_isolated(self):
        customer_a = Customer.objects.create(
            shop=self.shop_a,
            full_name="Shop A Customer",
            phone_number="+961 70-123-(456)",
        )

        customer_b = Customer.objects.create(
            shop=self.shop_b,
            full_name="Shop B Customer",
            phone_number="+961 71-123-(456)",
        )

        self.assertEqual(
            list(self.shop_a.customers.values_list("pk", flat=True)),
            [customer_a.pk],
        )

        self.assertEqual(
            list(self.shop_b.customers.values_list("pk", flat=True)),
            [customer_b.pk],
        )

    def test_empty_phone_number_is_rejected(self):
        with self.assertRaises(ValidationError):
            Customer.objects.create(
                shop=self.shop_a,
                full_name="Customer Without Phone",
                phone_number="",
            )


class CustomerViewTests(TestCase):
    """SCRUM-93: merchant-facing customer list/detail, scoped per shop."""

    def setUp(self):
        self.owner_a = User.objects.create_user(
            "customer-view-owner-a@example.com", "testpassword123",
            full_name="View Owner A", status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        self.owner_b = User.objects.create_user(
            "customer-view-owner-b@example.com", "testpassword123",
            full_name="View Owner B", status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        self.shop_a = Shop.objects.create(
            owner=self.owner_a, name="Shop A", slug="customer-view-shop-a",
            exchange_rate_lbp_per_usd=89500,
        )
        self.shop_b = Shop.objects.create(
            owner=self.owner_b, name="Shop B", slug="customer-view-shop-b",
            exchange_rate_lbp_per_usd=89500,
        )
        self.payment_method = ShopPaymentMethod.objects.create(
            shop=self.shop_a, method_name=ShopPaymentMethod.MethodName.CASH, enabled=True,
        )
        self.customer = Customer.objects.create(
            shop=self.shop_a, full_name="Returning Customer", phone_number="70123456",
        )
        self.other_shop_customer = Customer.objects.create(
            shop=self.shop_b, full_name="Other Shop Customer", phone_number="70999999",
        )

    def list_url(self, shop):
        return reverse("customers:list", kwargs={"shop_pk": shop.pk})

    def detail_url(self, shop, customer):
        return reverse(
            "customers:detail",
            kwargs={"shop_pk": shop.pk, "customer_pk": customer.pk},
        )

    def _create_order(self, *, customer, order_number, created_at=None, status=Order.Status.NEW):
        order = Order.objects.create(
            shop=customer.shop,
            customer=customer,
            selected_payment_method=self.payment_method,
            order_number=order_number,
            fulfillment_type=Order.FulfillmentType.PICKUP,
            status=status,
            customer_name_snapshot=customer.full_name,
            customer_phone_snapshot=customer.phone_number,
            zone_name_snapshot="",
            delivery_fee_snapshot=Decimal("0.00"),
            address_snapshot="",
            items_total=Decimal("20.00"),
            total=Decimal("20.00"),
            currency=Order.Currency.USD,
            fx_rate_snapshot=Decimal("89500.00"),
        )

        if created_at is not None:
            Order.objects.filter(pk=order.pk).update(created_at=created_at)
            order.refresh_from_db()

        return order

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(self.list_url(self.shop_a))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_list_shows_only_this_shops_customers(self):
        self.client.force_login(self.owner_a)

        response = self.client.get(self.list_url(self.shop_a))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [c.pk for c in response.context["customers"]],
            [self.customer.pk],
        )

    def test_empty_state_when_shop_has_no_customers(self):
        empty_shop = Shop.objects.create(
            owner=self.owner_a, name="Empty Shop", slug="customer-view-empty-shop",
            exchange_rate_lbp_per_usd=89500,
        )
        self.client.force_login(self.owner_a)

        response = self.client.get(self.list_url(empty_shop))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["customers"]), 0)
        self.assertContains(response, "No customers yet")

    def test_list_orders_by_newest_activity_first(self):
        other_customer = Customer.objects.create(
            shop=self.shop_a, full_name="Older Activity Customer", phone_number="70111222",
        )
        now = timezone.now()
        self._create_order(
            customer=other_customer, order_number="ORD-OLD-ACTIVITY",
            created_at=now - timedelta(days=5),
        )
        self._create_order(
            customer=self.customer, order_number="ORD-NEW-ACTIVITY",
            created_at=now,
        )
        self.client.force_login(self.owner_a)

        response = self.client.get(self.list_url(self.shop_a))

        self.assertEqual(
            [c.pk for c in response.context["customers"]],
            [self.customer.pk, other_customer.pk],
        )

    def test_list_shows_correct_order_count_and_last_order_date(self):
        self._create_order(customer=self.customer, order_number="ORD-COUNT-A")
        self._create_order(customer=self.customer, order_number="ORD-COUNT-B")
        self.client.force_login(self.owner_a)

        response = self.client.get(self.list_url(self.shop_a))

        customer = response.context["customers"][0]
        self.assertEqual(customer.order_count, 2)
        self.assertIsNotNone(customer.last_order_at)

    def test_detail_shows_customers_orders_newest_first(self):
        now = timezone.now()
        older = self._create_order(
            customer=self.customer, order_number="ORD-OLDER",
            created_at=now - timedelta(days=2),
        )
        newer = self._create_order(
            customer=self.customer, order_number="ORD-NEWER",
            created_at=now,
        )
        self.client.force_login(self.owner_a)

        response = self.client.get(self.detail_url(self.shop_a, self.customer))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [o.pk for o in response.context["orders"]],
            [newer.pk, older.pk],
        )

    def test_detail_links_to_existing_order_detail_page(self):
        order = self._create_order(customer=self.customer, order_number="ORD-LINK")
        self.client.force_login(self.owner_a)

        response = self.client.get(self.detail_url(self.shop_a, self.customer))

        self.assertContains(
            response,
            reverse(
                "orders:order-detail",
                kwargs={"shop_pk": self.shop_a.pk, "order_pk": order.pk},
            ),
        )

    def test_another_shops_customer_404s(self):
        self.client.force_login(self.owner_a)

        response = self.client.get(
            self.detail_url(self.shop_a, self.other_shop_customer)
        )

        self.assertEqual(response.status_code, 404)

    def test_viewing_another_owners_shop_list_404s(self):
        self.client.force_login(self.owner_a)

        response = self.client.get(self.list_url(self.shop_b))

        self.assertEqual(response.status_code, 404)
