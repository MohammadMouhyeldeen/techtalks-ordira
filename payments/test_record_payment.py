from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer
from orders.models import Order
from shops.models import Shop, ShopPaymentMethod, Subscription

from .models import Payment
from .services import record_payment


User = get_user_model()


class RecordPaymentTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="payment-owner@example.com",
            password="testpass123",
            full_name="Payment Owner",
            status=User.Status.ACTIVE,
        )

        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Payment Shop",
            slug="payment-shop",
            pickup_available=True,
            exchange_rate_lbp_per_usd=Decimal("90000.00"),
        )

        Subscription.objects.create(
            shop=self.shop,
            plan=Subscription.Plan.BASIC,
            status=Subscription.Status.ACTIVE,
            starts_on=date.today(),
        )

        self.customer = Customer.objects.create(
            shop=self.shop,
            full_name="Payment Customer",
            phone_number="70123456",
        )

        self.method = ShopPaymentMethod.objects.create(
            shop=self.shop,
            method_name=ShopPaymentMethod.MethodName.CASH,
            enabled=True,
        )

        self.order = Order.objects.create(
            shop=self.shop,
            customer=self.customer,
            selected_payment_method=self.method,
            order_number="ORD-PAYMENT-TEST",
            fulfillment_type=Order.FulfillmentType.PICKUP,
            status=Order.Status.NEW,
            customer_name_snapshot="Payment Customer",
            customer_phone_snapshot="70123456",
            zone_name_snapshot="",
            delivery_fee_snapshot=Decimal("0.00"),
            address_snapshot="",
            items_total=Decimal("15.00"),
            total=Decimal("15.00"),
            currency=Order.Currency.USD,
            fx_rate_snapshot=Decimal("90000.00"),
        )

        self.record_url = reverse(
            "payments:record-payment",
            kwargs={
                "shop_pk": self.shop.pk,
                "order_pk": self.order.pk,
            },
        )

        self.tracking_url = reverse(
            "track_order",
            kwargs={
                "shop_slug": self.shop.slug,
                "tracking_token": self.order.tracking_token,
            },
        )

    def test_exact_payment_in_order_currency_is_accepted(self):
        payment = record_payment(
            order=self.order,
            method=self.method,
            amount=Decimal("15.00"),
            currency=Payment.Currency.USD,
            note="Cash received.",
        )

        self.assertEqual(payment.status, Payment.Status.PAID)
        self.assertEqual(payment.amount, Decimal("15.00"))
        self.assertEqual(
            payment.amount_in_order_currency,
            Decimal("15.00"),
        )
        self.assertEqual(payment.method_name_snapshot, "Cash")
        self.assertEqual(payment.note, "Cash received.")
        self.assertIsNotNone(payment.received_at)

    def test_overpayment_is_rejected(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Payment amount cannot exceed the order total.",
        ):
            record_payment(
                order=self.order,
                method=self.method,
                amount=Decimal("16.00"),
                currency=Payment.Currency.USD,
            )

        self.assertFalse(
            Payment.objects.filter(order=self.order).exists()
        )

    def test_second_payment_is_rejected(self):
        record_payment(
            order=self.order,
            method=self.method,
            amount=Decimal("15.00"),
            currency=Payment.Currency.USD,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "A payment has already been recorded",
        ):
            record_payment(
                order=self.order,
                method=self.method,
                amount=Decimal("15.00"),
                currency=Payment.Currency.USD,
            )

        self.assertEqual(
            Payment.objects.filter(order=self.order).count(),
            1,
        )

    def test_cancelled_order_cannot_be_paid(self):
        self.order.status = Order.Status.CANCELLED
        self.order.cancellation_reason = "Customer cancelled."
        self.order.save(
            update_fields=[
                "status",
                "cancellation_reason",
            ]
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Cancelled orders cannot receive payments.",
        ):
            record_payment(
                order=self.order,
                method=self.method,
                amount=Decimal("15.00"),
                currency=Payment.Currency.USD,
            )

        self.assertFalse(
            Payment.objects.filter(order=self.order).exists()
        )

    def test_exact_lbp_payment_for_usd_order_is_accepted(self):
        payment = record_payment(
            order=self.order,
            method=self.method,
            amount=Decimal("1350000.00"),
            currency=Payment.Currency.LBP,
        )

        self.assertEqual(
            payment.amount_in_order_currency,
            Decimal("15.00"),
        )

    def test_partial_payment_is_rejected_without_creating_payment(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Payment must cover the full order total of 15.00 USD.",
        ):
            record_payment(
                order=self.order,
                method=self.method,
                amount=Decimal("1.00"),
                currency=Payment.Currency.USD,
            )

        self.assertFalse(
            Payment.objects.filter(order=self.order).exists()
        )

    def test_rejected_partial_payment_can_be_followed_by_full_payment(self):
        with self.assertRaises(ValidationError):
            record_payment(
                order=self.order,
                method=self.method,
                amount=Decimal("1.00"),
                currency=Payment.Currency.USD,
            )

        payment = record_payment(
            order=self.order,
            method=self.method,
            amount=Decimal("15.00"),
            currency=Payment.Currency.USD,
        )

        self.assertEqual(payment.status, Payment.Status.PAID)
        self.assertEqual(payment.amount, Decimal("15.00"))
        self.assertEqual(
            Payment.objects.filter(order=self.order).count(),
            1,
        )

    def test_usd_payment_for_lbp_order_accepts_rounding_tolerance(self):
        self.order.items_total = Decimal("1000.00")
        self.order.total = Decimal("1000.00")
        self.order.currency = Order.Currency.LBP
        self.order.save(
            update_fields=[
                "items_total",
                "total",
                "currency",
            ]
        )

        payment = record_payment(
            order=self.order,
            method=self.method,
            amount=Decimal("0.01"),
            currency=Payment.Currency.USD,
        )

        self.assertEqual(payment.status, Payment.Status.PAID)
        self.assertEqual(payment.amount, Decimal("0.01"))
        self.assertEqual(
            payment.amount_in_order_currency,
            Decimal("900.00"),
        )

    def test_cross_currency_overpayment_beyond_tolerance_is_rejected(self):
        self.order.items_total = Decimal("1350000.00")
        self.order.total = Decimal("1350000.00")
        self.order.currency = Order.Currency.LBP
        self.order.save(
            update_fields=[
                "items_total",
                "total",
                "currency",
            ]
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Payment amount cannot exceed the order total.",
        ):
            record_payment(
                order=self.order,
                method=self.method,
                amount=Decimal("15.02"),
                currency=Payment.Currency.USD,
            )

        self.assertFalse(
            Payment.objects.filter(order=self.order).exists()
        )

    def test_cross_currency_underpayment_beyond_tolerance_is_rejected(self):
        self.order.items_total = Decimal("1350000.00")
        self.order.total = Decimal("1350000.00")
        self.order.currency = Order.Currency.LBP
        self.order.save(
            update_fields=[
                "items_total",
                "total",
                "currency",
            ]
        )

        with self.assertRaisesMessage(
            ValidationError,
            (
                "Payment must cover the full order total of "
                "1350000.00 LBP."
            ),
        ):
            record_payment(
                order=self.order,
                method=self.method,
                amount=Decimal("14.98"),
                currency=Payment.Currency.USD,
            )

        self.assertFalse(
            Payment.objects.filter(order=self.order).exists()
        )
    def test_non_owner_receives_404(self):
        other_owner = User.objects.create_user(
            email="other-owner@example.com",
            password="testpass123",
            full_name="Other Owner",
            status=User.Status.ACTIVE,
        )

        self.client.force_login(other_owner)

        response = self.client.post(
            self.record_url,
            {
                "method": self.method.pk,
                "amount": "15.00",
                "currency": Payment.Currency.USD,
                "note": "",
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            Payment.objects.filter(order=self.order).exists()
        )

    def test_record_payment_view_accepts_post(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.record_url,
            {
                "method": self.method.pk,
                "amount": "15.00",
                "currency": Payment.Currency.USD,
                "note": "Paid at the shop.",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "orders:order-detail",
                kwargs={
                    "shop_pk": self.shop.pk,
                    "order_pk": self.order.pk,
                },
            ),
        )

        payment = Payment.objects.get(order=self.order)

        self.assertEqual(payment.status, Payment.Status.PAID)
        self.assertEqual(payment.note, "Paid at the shop.")

    def test_record_payment_view_rejects_get(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.record_url)

        self.assertEqual(response.status_code, 405)
        self.assertFalse(
            Payment.objects.filter(order=self.order).exists()
        )

    def test_tracking_page_shows_unpaid_without_payment(self):
        response = self.client.get(self.tracking_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "<strong>Unpaid</strong>",
            html=True,
        )
        self.assertNotContains(
            response,
            "<strong>Paid</strong>",
            html=True,
        )

    def test_tracking_page_shows_paid_after_payment_recorded(self):
        record_payment(
            order=self.order,
            method=self.method,
            amount=Decimal("15.00"),
            currency=Payment.Currency.USD,
        )

        response = self.client.get(self.tracking_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "<strong>Paid</strong>",
            html=True,
        )
        self.assertNotContains(
            response,
            "<strong>Unpaid</strong>",
            html=True,
        )
