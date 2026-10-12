from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from accounts.models import User
from shops.models import Shop

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
