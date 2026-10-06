from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, TransactionTestCase
from django.db import close_old_connections

from products.models import (
    Category,
    Product,
    ProductVariant,
    StockMovement,
)
from shops.models import Shop, ShopPaymentMethod

from .models import Order
from .services import cancel_order, create_order


User = get_user_model()

class OrderCancellationServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="cancellation-owner@example.com",
            password="testpass123",
            full_name="Cancellation Owner",
            status=User.Status.ACTIVE,
        )

        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Cancellation Shop",
            slug="cancellation-shop",
            pickup_available=True,
            exchange_rate_lbp_per_usd=Decimal("90000.00"),
        )

        self.category = Category.objects.create(
            shop=self.shop,
            name="Clothing",
        )

        self.product = Product.objects.create(
            shop=self.shop,
            category=self.category,
            name="Classic T-shirt",
        )

        self.variant = ProductVariant.objects.create(
            product=self.product,
            color="Black",
            size="Medium",
            unit_price=Decimal("10.00"),
            currency=ProductVariant.Currency.USD,
            stock_quantity=10,
            low_stock_threshold=1,
        )

        self.payment_method = ShopPaymentMethod.objects.create(
            shop=self.shop,
            method_name=ShopPaymentMethod.MethodName.CASH,
            enabled=True,
        )

        self.order = create_order(
            shop=self.shop,
            customer_name="Cancellation Customer",
            customer_phone="03123456",
            fulfillment_type=Order.FulfillmentType.PICKUP,
            selected_payment_method=self.payment_method,
            items=[
                {
                    "variant_id": self.variant.pk,
                    "quantity": 2,
                },
            ],
            currency=Order.Currency.USD,
        )

    def test_cancellation_restores_stock_and_records_movement(self):
        cancelled_order = cancel_order(
            self.order,
            "Customer requested cancellation.",
        )

        self.order.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(
            cancelled_order.status,
            Order.Status.CANCELLED,
        )
        self.assertEqual(
            self.order.status,
            Order.Status.CANCELLED,
        )
        self.assertEqual(
            self.order.cancellation_reason,
            "Customer requested cancellation.",
        )
        self.assertIsNotNone(self.order.stock_restored_at)
        self.assertEqual(self.variant.stock_quantity, 10)

        movement = StockMovement.objects.get(
            variant=self.variant,
            reason=StockMovement.Reason.CANCELLATION,
        )

        self.assertEqual(movement.change_qty, 2)
        self.assertIsNone(movement.created_by)

    def test_second_cancellation_does_not_restore_stock_again(self):
        cancel_order(
            self.order,
            "Customer requested cancellation.",
        )

        self.order.refresh_from_db()
        first_restored_at = self.order.stock_restored_at

        cancel_order(
            self.order,
            "Repeated cancellation.",
        )

        self.order.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(self.variant.stock_quantity, 10)
        self.assertEqual(
            self.order.stock_restored_at,
            first_restored_at,
        )
        self.assertEqual(
            self.order.cancellation_reason,
            "Customer requested cancellation.",
        )
        self.assertEqual(
            StockMovement.objects.filter(
                variant=self.variant,
                reason=StockMovement.Reason.CANCELLATION,
            ).count(),
            1,
        )

    def test_completed_order_cannot_be_cancelled(self):
        self.order.status = Order.Status.COMPLETED
        self.order.save(update_fields=["status"])

        with self.assertRaisesMessage(
            ValidationError,
            "Completed orders cannot be cancelled.",
        ):
            cancel_order(
                self.order,
                "Attempted cancellation.",
            )

        self.order.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.Status.COMPLETED,
        )
        self.assertIsNone(self.order.stock_restored_at)
        self.assertEqual(self.variant.stock_quantity, 8)
        self.assertFalse(
            StockMovement.objects.filter(
                variant=self.variant,
                reason=StockMovement.Reason.CANCELLATION,
            ).exists()
        )

    def test_order_item_without_variant_is_skipped(self):
        order_item = self.order.items.get()
        order_item.variant = None
        order_item.save(update_fields=["variant"])

        cancel_order(
            self.order,
            "Variant is no longer available.",
        )

        self.order.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.Status.CANCELLED,
        )
        self.assertIsNotNone(self.order.stock_restored_at)
        self.assertEqual(self.variant.stock_quantity, 8)
        self.assertFalse(
            StockMovement.objects.filter(
                variant=self.variant,
                reason=StockMovement.Reason.CANCELLATION,
            ).exists()
        )

    def test_cancellation_reason_is_required(self):
        with self.assertRaisesMessage(
            ValidationError,
            "A cancellation reason is required.",
        ):
            cancel_order(self.order, "   ")

        self.order.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(self.order.status, Order.Status.NEW)
        self.assertIsNone(self.order.stock_restored_at)
        self.assertEqual(self.variant.stock_quantity, 8)

class OrderCancellationConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.owner = User.objects.create_user(
            email="concurrent-cancellation-owner@example.com",
            password="testpass123",
            full_name="Concurrent Cancellation Owner",
            status=User.Status.ACTIVE,
        )

        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Concurrent Cancellation Shop",
            slug="concurrent-cancellation-shop",
            pickup_available=True,
            exchange_rate_lbp_per_usd=Decimal("90000.00"),
        )

        self.category = Category.objects.create(
            shop=self.shop,
            name="Clothing",
        )

        self.product = Product.objects.create(
            shop=self.shop,
            category=self.category,
            name="Concurrent T-shirt",
        )

        self.variant = ProductVariant.objects.create(
            product=self.product,
            color="Black",
            size="Medium",
            unit_price=Decimal("10.00"),
            currency=ProductVariant.Currency.USD,
            stock_quantity=10,
            low_stock_threshold=1,
        )

        self.payment_method = ShopPaymentMethod.objects.create(
            shop=self.shop,
            method_name=ShopPaymentMethod.MethodName.CASH,
            enabled=True,
        )

        self.order = create_order(
            shop=self.shop,
            customer_name="Concurrent Customer",
            customer_phone="03999999",
            fulfillment_type=Order.FulfillmentType.PICKUP,
            selected_payment_method=self.payment_method,
            items=[
                {
                    "variant_id": self.variant.pk,
                    "quantity": 2,
                },
            ],
            currency=Order.Currency.USD,
        )

    def _cancel_from_separate_connection(self, barrier):
        close_old_connections()

        try:
            order = Order.objects.get(pk=self.order.pk)
            barrier.wait(timeout=10)

            cancel_order(
                order,
                "Concurrent cancellation.",
            )
        finally:
            close_old_connections()

    def test_concurrent_cancellations_restore_stock_only_once(self):
        barrier = Barrier(2)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    self._cancel_from_separate_connection,
                    barrier,
                )
                for _ in range(2)
            ]

            for future in futures:
                future.result(timeout=20)

        self.order.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.Status.CANCELLED,
        )
        self.assertIsNotNone(self.order.stock_restored_at)
        self.assertEqual(self.variant.stock_quantity, 10)
        self.assertEqual(
            StockMovement.objects.filter(
                variant=self.variant,
                reason=StockMovement.Reason.CANCELLATION,
            ).count(),
            1,
        )
