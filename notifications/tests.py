from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from orders.models import Order
from orders.services import create_order

from products.models import (
    Category,
    Product,
    ProductVariant,
    StockMovement,
)
from products.services import adjust_variant_stock
from shops.models import Shop, ShopPaymentMethod

from .models import Notification


User = get_user_model()


class LowStockAdjustmentTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="notification-owner@example.com",
            password="testpass123",
            full_name="Notification Owner",
            status=User.Status.ACTIVE,
        )

        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Notification Shop",
            slug="notification-shop",
            whatsapp="96170123456",
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
            stock_quantity=5,
            low_stock_threshold=3,
        )
        self.payment_method = ShopPaymentMethod.objects.create(
            shop=self.shop,
            method_name=ShopPaymentMethod.MethodName.CASH,
            enabled=True,
        )

    def adjust_stock(self, change_qty):
        return adjust_variant_stock(
            variant=self.variant,
            change_qty=change_qty,
            reason=StockMovement.Reason.ADJUSTMENT,
            created_by=self.owner,
        )

    def create_pickup_order(self):
        return create_order(
            shop=self.shop,
            customer_name="Notification Customer",
            customer_phone="70123456",
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

    def test_crossing_threshold_creates_low_stock_notification(self):
        self.adjust_stock(-2)

        self.variant.refresh_from_db()

        self.assertEqual(self.variant.stock_quantity, 3)
        self.assertEqual(Notification.objects.count(), 1)

        notification = Notification.objects.get()

        self.assertEqual(
            notification.notification_type,
            Notification.Type.LOW_STOCK,
        )
        self.assertEqual(notification.shop, self.shop)
        self.assertEqual(notification.recipient, self.owner)
        self.assertFalse(notification.is_read)
        self.assertIn("Classic T-shirt", notification.message)
        self.assertIn("3 remaining", notification.message)

    def test_staying_low_does_not_create_duplicate(self):
        self.adjust_stock(-2)
        self.adjust_stock(-1)

        self.variant.refresh_from_db()

        self.assertEqual(self.variant.stock_quantity, 2)
        self.assertEqual(Notification.objects.count(), 1)

    def test_restock_then_drop_creates_another_notification(self):
        self.adjust_stock(-2)
        self.adjust_stock(3)
        self.adjust_stock(-3)

        self.variant.refresh_from_db()

        self.assertEqual(self.variant.stock_quantity, 3)
        self.assertEqual(Notification.objects.count(), 2)

    def test_stock_remaining_above_threshold_creates_none(self):
        self.adjust_stock(-1)

        self.variant.refresh_from_db()

        self.assertEqual(self.variant.stock_quantity, 4)
        self.assertEqual(Notification.objects.count(), 0)

    def test_failed_stock_transaction_leaves_no_notification(self):
        with patch(
            "products.services.StockMovement.objects.create",
            side_effect=RuntimeError("Simulated failure"),
        ):
            with self.assertRaisesMessage(
                RuntimeError,
                "Simulated failure",
            ):
                self.adjust_stock(-2)

        self.variant.refresh_from_db()

        self.assertEqual(self.variant.stock_quantity, 5)
        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_checkout_crossing_threshold_creates_notification(self):
        order = self.create_pickup_order()

        self.variant.refresh_from_db()

        self.assertIsNotNone(order.pk)
        self.assertEqual(self.variant.stock_quantity, 3)
        self.assertEqual(Notification.objects.count(), 1)

        notification = Notification.objects.get()

        self.assertEqual(
            notification.notification_type,
            Notification.Type.LOW_STOCK,
        )
        self.assertEqual(notification.shop, self.shop)
        self.assertEqual(notification.recipient, self.owner)

    def test_failed_checkout_rolls_back_low_stock_notification(self):
        with patch(
            "orders.services.StockMovement.objects.create",
            side_effect=RuntimeError("Simulated checkout failure"),
        ):
            with self.assertRaisesMessage(
                RuntimeError,
                "Simulated checkout failure",
            ):
                self.create_pickup_order()

        self.variant.refresh_from_db()

        self.assertEqual(self.variant.stock_quantity, 5)
        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)

class NotificationViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="notification-view-owner@example.com",
            password="testpass123",
            full_name="Notification View Owner",
            status=User.Status.ACTIVE,
        )
        self.other_owner = User.objects.create_user(
            email="other-notification-owner@example.com",
            password="testpass123",
            full_name="Other Notification Owner",
            status=User.Status.ACTIVE,
        )

        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Notification View Shop",
            slug="notification-view-shop",
            whatsapp="96170111111",
            pickup_available=True,
            exchange_rate_lbp_per_usd=Decimal("90000.00"),
        )
        self.other_shop = Shop.objects.create(
            owner=self.other_owner,
            name="Other Notification Shop",
            slug="other-notification-shop",
            whatsapp="96170222222",
            pickup_available=True,
            exchange_rate_lbp_per_usd=Decimal("90000.00"),
        )

        self.owner_unread = Notification.objects.create(
            shop=self.shop,
            recipient=self.owner,
            notification_type=Notification.Type.LOW_STOCK,
            message="Owner unread notification",
        )
        self.owner_read = Notification.objects.create(
            shop=self.shop,
            recipient=self.owner,
            notification_type=Notification.Type.LOW_STOCK,
            message="Owner read notification",
            is_read=True,
        )
        self.other_unread = Notification.objects.create(
            shop=self.other_shop,
            recipient=self.other_owner,
            notification_type=Notification.Type.LOW_STOCK,
            message="Other owner notification",
        )

        self.list_url = reverse("notifications:list")
        self.mark_all_url = reverse(
            "notifications:mark-all-read"
        )

    def test_notification_list_is_recipient_scoped(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Owner unread notification",
        )
        self.assertContains(
            response,
            "Owner read notification",
        )
        self.assertNotContains(
            response,
            "Other owner notification",
        )

    def test_unread_count_is_available_in_page_context(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.context["unread_notifications"],
            1,
        )
        self.assertContains(response, self.list_url)

    def test_mark_all_read_only_updates_current_recipient(self):
        self.client.force_login(self.owner)

        response = self.client.post(self.mark_all_url)

        self.assertRedirects(response, self.list_url)

        self.owner_unread.refresh_from_db()
        self.owner_read.refresh_from_db()
        self.other_unread.refresh_from_db()

        self.assertTrue(self.owner_unread.is_read)
        self.assertTrue(self.owner_read.is_read)
        self.assertFalse(self.other_unread.is_read)

    def test_mark_all_read_rejects_get(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.mark_all_url)

        self.assertEqual(response.status_code, 405)
        self.owner_unread.refresh_from_db()
        self.assertFalse(self.owner_unread.is_read)