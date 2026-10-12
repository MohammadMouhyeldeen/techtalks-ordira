import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.template.loader import render_to_string
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from customers.models import Customer
from products.models import (
    Category,
    Product,
    ProductVariant,
    StockMovement,
)
from shops.models import DeliveryZone, Shop, ShopPaymentMethod, Subscription

from .models import Order, OrderItem
from .services import(
    cancel_order,
    create_order,
    transition_order_status,
)
from .views import _order_context, _payment_method_display

from unittest.mock import patch


User = get_user_model()


class CheckoutServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="testpass123",
            full_name="Shop Owner",
            status=User.Status.ACTIVE,
        )

        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Reem Shop",
            slug="reem-shop",
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

        self.usd_variant = ProductVariant.objects.create(
            product=self.product,
            color="Black",
            size="Medium",
            unit_price=Decimal("10.00"),
            currency=ProductVariant.Currency.USD,
            stock_quantity=5,
            low_stock_threshold=1,
        )

        self.lbp_variant = ProductVariant.objects.create(
            product=self.product,
            color="White",
            size="Large",
            unit_price=Decimal("900000.00"),
            currency=ProductVariant.Currency.LBP,
            stock_quantity=4,
            low_stock_threshold=1,
        )

        self.delivery_zone = DeliveryZone.objects.create(
            shop=self.shop,
            area_name="Beirut",
            fee=Decimal("3.00"),
        )

        self.payment_method = ShopPaymentMethod.objects.create(
            shop=self.shop,
            method_name=ShopPaymentMethod.MethodName.CASH,
            enabled=True,
        )

    def create_delivery_order(self, **overrides):
        data = {
            "shop": self.shop,
            "customer_name": "Reem Customer",
            "customer_phone": "03123456",
            "fulfillment_type": Order.FulfillmentType.DELIVERY,
            "selected_payment_method": self.payment_method,
            "items": [
                {
                    "variant_id": self.usd_variant.pk,
                    "quantity": 2,
                },
                {
                    "variant_id": self.lbp_variant.pk,
                    "quantity": 1,
                },
            ],
            "currency": Order.Currency.USD,
            "delivery_zone": self.delivery_zone,
            "address": "Beirut, Lebanon",
        }
        data.update(overrides)
        return create_order(**data)

    def test_checkout_creates_order_items_and_snapshots(self):
        order = self.create_delivery_order()

        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderItem.objects.count(), 2)
        self.assertEqual(Customer.objects.count(), 1)

        self.assertEqual(order.status, Order.Status.NEW)
        self.assertEqual(order.items_total, Decimal("30.00"))
        self.assertEqual(
            order.delivery_fee_snapshot,
            Decimal("3.00"),
        )
        self.assertEqual(order.total, Decimal("33.00"))
        self.assertEqual(order.currency, Order.Currency.USD)
        self.assertEqual(
            order.fx_rate_snapshot,
            Decimal("90000.00"),
        )
        self.assertEqual(order.zone_name_snapshot, "Beirut")
        self.assertEqual(order.address_snapshot, "Beirut, Lebanon")

        self.assertTrue(order.order_number.startswith("ORD-"))
        self.assertIsNotNone(order.tracking_token)

        usd_item = order.items.get(variant=self.usd_variant)
        self.assertEqual(
            usd_item.product_name_snapshot,
            "Classic T-shirt",
        )
        self.assertEqual(usd_item.color_snapshot, "Black")
        self.assertEqual(usd_item.size_snapshot, "Medium")
        self.assertEqual(
            usd_item.unit_price_snapshot,
            Decimal("10.00"),
        )
        self.assertEqual(usd_item.quantity, 2)
        self.assertEqual(
            usd_item.line_total,
            Decimal("20.00"),
        )

        lbp_item = order.items.get(variant=self.lbp_variant)
        self.assertEqual(
            lbp_item.unit_price_snapshot,
            Decimal("10.00"),
        )
        self.assertEqual(
            lbp_item.line_total,
            Decimal("10.00"),
        )

    def test_checkout_deducts_stock_and_creates_movements(self):
        self.create_delivery_order()

        self.usd_variant.refresh_from_db()
        self.lbp_variant.refresh_from_db()

        self.assertEqual(self.usd_variant.stock_quantity, 3)
        self.assertEqual(self.lbp_variant.stock_quantity, 3)

        usd_movement = StockMovement.objects.get(
            variant=self.usd_variant,
        )
        self.assertEqual(usd_movement.change_qty, -2)
        self.assertEqual(
            usd_movement.reason,
            StockMovement.Reason.SALE,
        )

        lbp_movement = StockMovement.objects.get(
            variant=self.lbp_variant,
        )
        self.assertEqual(lbp_movement.change_qty, -1)
        self.assertEqual(
            lbp_movement.reason,
            StockMovement.Reason.SALE,
        )

    def test_checkout_converts_totals_to_lbp(self):
        order = self.create_delivery_order(
            items=[
                {
                    "variant_id": self.usd_variant.pk,
                    "quantity": 1,
                },
            ],
            currency=Order.Currency.LBP,
        )

        self.assertEqual(
            order.items_total,
            Decimal("900000.00"),
        )
        self.assertEqual(
            order.delivery_fee_snapshot,
            Decimal("270000.00"),
        )
        self.assertEqual(
            order.total,
            Decimal("1170000.00"),
        )

    def test_pickup_order_has_no_delivery_fee(self):
        order = create_order(
            shop=self.shop,
            customer_name="Pickup Customer",
            customer_phone="03777777",
            fulfillment_type=Order.FulfillmentType.PICKUP,
            selected_payment_method=self.payment_method,
            items=[
                {
                    "variant_id": self.usd_variant.pk,
                    "quantity": 1,
                },
            ],
            currency=Order.Currency.USD,
        )

        self.assertIsNone(order.delivery_zone)
        self.assertEqual(order.zone_name_snapshot, "")
        self.assertEqual(order.address_snapshot, "")
        self.assertEqual(
            order.delivery_fee_snapshot,
            Decimal("0.00"),
        )
        self.assertEqual(order.items_total, Decimal("10.00"))
        self.assertEqual(order.total, Decimal("10.00"))

    def test_insufficient_stock_rolls_back_checkout(self):
        original_stock = self.usd_variant.stock_quantity

        with self.assertRaisesMessage(
            ValidationError,
            "Not enough stock",
        ):
            self.create_delivery_order(
                items=[
                    {
                        "variant_id": self.usd_variant.pk,
                        "quantity": original_stock + 1,
                    },
                ],
            )

        self.usd_variant.refresh_from_db()

        self.assertEqual(
            self.usd_variant.stock_quantity,
            original_stock,
        )
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)
        self.assertEqual(Customer.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_duplicate_variant_entries_are_combined(self):
        order = self.create_delivery_order(
            items=[
                {
                    "variant_id": self.usd_variant.pk,
                    "quantity": 1,
                },
                {
                    "variant_id": self.usd_variant.pk,
                    "quantity": 2,
                },
            ],
        )

        self.assertEqual(order.items.count(), 1)

        item = order.items.get()
        self.assertEqual(item.quantity, 3)
        self.assertEqual(item.line_total, Decimal("30.00"))

        self.usd_variant.refresh_from_db()
        self.assertEqual(self.usd_variant.stock_quantity, 2)

        movement = StockMovement.objects.get(
            variant=self.usd_variant,
        )
        self.assertEqual(movement.change_qty, -3)

    def test_fractional_quantity_is_rejected(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Item quantity must be a positive integer.",
        ):
            self.create_delivery_order(
                items=[
                    {
                        "variant_id": self.usd_variant.pk,
                        "quantity": 1.5,
                    },
                ],
            )

        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_variant_from_another_shop_is_rejected(self):
        other_owner = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            full_name="Other Owner",
            status=User.Status.ACTIVE,
        )
        other_shop = Shop.objects.create(
            owner=other_owner,
            name="Other Shop",
            slug="other-shop",
            pickup_available=True,
            exchange_rate_lbp_per_usd=Decimal("90000.00"),
        )
        other_category = Category.objects.create(
            shop=other_shop,
            name="Other Category",
        )
        other_product = Product.objects.create(
            shop=other_shop,
            category=other_category,
            name="Other Product",
        )
        other_variant = ProductVariant.objects.create(
            product=other_product,
            color="Blue",
            size="Small",
            unit_price=Decimal("5.00"),
            currency=ProductVariant.Currency.USD,
            stock_quantity=5,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "All product variants must belong",
        ):
            self.create_delivery_order(
                items=[
                    {
                        "variant_id": other_variant.pk,
                        "quantity": 1,
                    },
                ],
            )

        other_variant.refresh_from_db()
        self.assertEqual(other_variant.stock_quantity, 5)
        self.assertEqual(Order.objects.count(), 0)

    def test_disabled_payment_method_is_rejected(self):
        self.payment_method.enabled = False
        self.payment_method.save(update_fields=["enabled"])

        with self.assertRaisesMessage(
            ValidationError,
            "The selected payment method is not available",
        ):
            self.create_delivery_order()

        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_tracking_tokens_are_generated_and_unique(self):
        first_order = self.create_delivery_order()
        second_order = self.create_delivery_order(
            customer_phone="03999999",
        )

        self.assertIsNotNone(first_order.tracking_token)
        self.assertIsNotNone(second_order.tracking_token)
        self.assertNotEqual(
            first_order.tracking_token,
            second_order.tracking_token,
        )

    def test_inactive_variant_is_rejected(self):
        self.usd_variant.is_active = False
        self.usd_variant.save(update_fields=["is_active"])

        with self.assertRaisesMessage(
            ValidationError,
            "is no longer available",
        ):
            self.create_delivery_order(
                items=[
                    {
                        "variant_id": self.usd_variant.pk,
                        "quantity": 1,
                    },
                ],
            )

        self.assertEqual(Order.objects.count(), 0)

    def test_inactive_product_is_rejected(self):
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])

        with self.assertRaisesMessage(
            ValidationError,
            "is no longer available",
        ):
            self.create_delivery_order(
                items=[
                    {
                        "variant_id": self.usd_variant.pk,
                        "quantity": 1,
                    },
                ],
            )

        self.assertEqual(Order.objects.count(), 0)

    def test_delivery_zone_from_another_shop_is_rejected(self):
        other_owner = User.objects.create_user(
            email="zone-owner@example.com",
            password="testpass123",
            full_name="Zone Owner",
            status=User.Status.ACTIVE,
        )
        other_shop = Shop.objects.create(
            owner=other_owner,
            name="Zone Shop",
            slug="zone-shop",
            pickup_available=True,
            exchange_rate_lbp_per_usd=Decimal("90000.00"),
        )
        other_zone = DeliveryZone.objects.create(
            shop=other_shop,
            area_name="Tripoli",
            fee=Decimal("5.00"),
        )

        with self.assertRaisesMessage(
            ValidationError,
            "The selected delivery zone is not available.",
        ):
            self.create_delivery_order(
                delivery_zone=other_zone,
            )

        self.assertEqual(Order.objects.count(), 0)

    def test_pickup_order_with_delivery_zone_is_rejected(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Pickup orders cannot have a delivery zone.",
        ):
            self.create_delivery_order(
                fulfillment_type=Order.FulfillmentType.PICKUP,
                delivery_zone=self.delivery_zone,
                address="",
            )

        self.assertEqual(Order.objects.count(), 0)

    def test_zero_and_negative_quantities_are_rejected(self):
        for quantity in (0, -1):
            with self.subTest(quantity=quantity):
                with self.assertRaisesMessage(
                    ValidationError,
                    "Item quantity must be a positive integer.",
                ):
                    self.create_delivery_order(
                        items=[
                            {
                                "variant_id": self.usd_variant.pk,
                                "quantity": quantity,
                            },
                        ],
                    )

        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_variant_query_uses_for_update_lock(self):
        with CaptureQueriesContext(connection) as captured:
            self.create_delivery_order(
                items=[
                    {
                        "variant_id": self.usd_variant.pk,
                        "quantity": 1,
                    },
                ],
            )

        variant_queries = [
            query["sql"]
            for query in captured.captured_queries
            if "products_productvariant" in query["sql"].lower()
        ]

        self.assertTrue(
            any(
                "FOR UPDATE" in query.upper()
                for query in variant_queries
            ),
            "Expected the ProductVariant query to use FOR UPDATE.",
        )


    def test_transition_new_to_preparing(self):
        order = self.create_delivery_order()

        updated_order = transition_order_status(
            order,
            Order.Status.PREPARING,
        )

        self.assertEqual(updated_order.status, Order.Status.PREPARING)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PREPARING)

    def test_transition_preparing_to_handed_to_delivery(self):
        order = self.create_delivery_order()
        transition_order_status(order, Order.Status.PREPARING)

        updated_order = transition_order_status(
            order,
            Order.Status.HANDED_TO_DELIVERY,
        )

        self.assertEqual(
            updated_order.status,
            Order.Status.HANDED_TO_DELIVERY,
        )

    def test_transition_handed_to_delivery_to_completed(self):
        order = self.create_delivery_order()
        transition_order_status(order, Order.Status.PREPARING)
        transition_order_status(
            order,
            Order.Status.HANDED_TO_DELIVERY,
        )

        updated_order = transition_order_status(
            order,
            Order.Status.COMPLETED,
        )

        self.assertEqual(updated_order.status, Order.Status.COMPLETED)

    def test_transition_rejects_skipped_and_backward_moves(self):
        order = self.create_delivery_order()

        invalid_moves = [
            Order.Status.HANDED_TO_DELIVERY,
            Order.Status.COMPLETED,
        ]
        for target_status in invalid_moves:
            with self.subTest(target_status=target_status):
                with self.assertRaisesMessage(
                    ValidationError,
                    "Order can only move from New Order to Preparing.",
                ):
                    transition_order_status(order, target_status)

        transition_order_status(order, Order.Status.PREPARING)

        with self.assertRaisesMessage(
            ValidationError,
            "Order can only move from Preparing to Handed to Delivery.",
        ):
            transition_order_status(order, Order.Status.NEW)

        with self.assertRaises(ValidationError):
            transition_order_status(order, Order.Status.COMPLETED)

    def test_transition_rejects_invalid_target_status(self):
        order = self.create_delivery_order()

        with self.assertRaisesMessage(
            ValidationError,
            "Invalid target order status.",
        ):
            transition_order_status(order, "INVALID")

    def test_completed_order_is_terminal(self):
        order = self.create_delivery_order()
        transition_order_status(order, Order.Status.PREPARING)
        transition_order_status(
            order,
            Order.Status.HANDED_TO_DELIVERY,
        )
        transition_order_status(order, Order.Status.COMPLETED)

        with self.assertRaisesMessage(
            ValidationError,
            "Completed orders are terminal and cannot be changed.",
        ):
            transition_order_status(order, Order.Status.PREPARING)

    def test_cancelled_order_is_terminal(self):
        order = self.create_delivery_order()
        cancel_order(order, "Customer requested cancellation.")

        with self.assertRaisesMessage(
            ValidationError,
            "Cancelled orders are terminal and cannot be changed.",
        ):
            transition_order_status(order, Order.Status.PREPARING)


    def test_merchant_can_advance_order_status(self):
        order = self.create_delivery_order()
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "orders:order-action",
                args=[self.shop.pk, order.pk],
            ),
            {
                "action": "advance",
                "target_status": Order.Status.PREPARING,
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "orders:order-detail",
                args=[self.shop.pk, order.pk],
            ),
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PREPARING)

    def test_merchant_cannot_skip_order_status(self):
        order = self.create_delivery_order()
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "orders:order-action",
                args=[self.shop.pk, order.pk],
            ),
            {
                "action": "advance",
                "target_status": Order.Status.HANDED_TO_DELIVERY,
            },
            follow=True,
        )

        self.assertContains(
            response,
            "Order can only move from New Order to Preparing.",
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.NEW)

    def test_order_action_rejects_get(self):
        order = self.create_delivery_order()
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse(
                "orders:order-action",
                args=[self.shop.pk, order.pk],
            ),
        )

        self.assertEqual(response.status_code, 405)

    def test_order_action_requires_csrf_token(self):
        order = self.create_delivery_order()
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)

        response = csrf_client.post(
            reverse(
                "orders:order-action",
                args=[self.shop.pk, order.pk],
            ),
            {
                "action": "advance",
                "target_status": Order.Status.PREPARING,
            },
        )

        self.assertEqual(response.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.NEW)

    @patch("orders.views.cancel_order")
    def test_cancel_action_delegates_to_scrum77_service(
        self,
        cancel_order_mock,
    ):
        order = self.create_delivery_order()
        self.client.force_login(self.owner)
        reason = "Customer requested cancellation."

        response = self.client.post(
            reverse(
                "orders:order-action",
                args=[self.shop.pk, order.pk],
            ),
            {
                "action": "cancel",
                "cancellation_reason": reason,
            },
        )

        self.assertEqual(response.status_code, 302)
        cancel_order_mock.assert_called_once()
        called_order, called_reason = cancel_order_mock.call_args.args
        self.assertEqual(called_order.pk, order.pk)
        self.assertEqual(called_reason, reason)

    def test_rejected_cancel_displays_service_error(self):
        order = self.create_delivery_order()
        transition_order_status(order, Order.Status.PREPARING)
        transition_order_status(
            order,
            Order.Status.HANDED_TO_DELIVERY,
        )
        transition_order_status(order, Order.Status.COMPLETED)

        self.client.force_login(self.owner)
        response = self.client.post(
            reverse(
                "orders:order-action",
                args=[self.shop.pk, order.pk],
            ),
            {
                "action": "cancel",
                "cancellation_reason": "Customer requested cancellation.",
            },
            follow=True,
        )

        self.assertContains(
            response,
            "Completed orders cannot be cancelled.",
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)

    def test_order_action_returns_404_for_wrong_shop(self):
        order = self.create_delivery_order()

        other_shop = Shop.objects.create(
            owner=self.owner,
            name="Other Shop",
            slug="other-shop",
            pickup_available=True,
            exchange_rate_lbp_per_usd=Decimal("90000.00"),
        )

        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "orders:order-action",
                args=[other_shop.pk, order.pk],
            ),
            {
                "action": "advance",
                "target_status": Order.Status.PREPARING,
            },
        )

        self.assertEqual(response.status_code, 404)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.NEW)

    def test_order_detail_shows_only_valid_actions(self):
        order = self.create_delivery_order()
        self.client.force_login(self.owner)

        detail_url = reverse(
            "orders:order-detail",
            args=[self.shop.pk, order.pk],
        )

        def assert_actions_visible(*visible, absent=()):
            response = self.client.get(detail_url)
            self.assertEqual(response.status_code, 200)

            for label in visible:
                self.assertContains(response, label)

            for label in absent:
                self.assertNotContains(response, label)

        # NEW
        assert_actions_visible(
            "Mark as Preparing",
            "Cancel Order",
            absent=("Hand to Delivery", "Mark as Completed"),
        )

        # PREPARING
        transition_order_status(order, Order.Status.PREPARING)
        assert_actions_visible(
            "Hand to Delivery",
            "Cancel Order",
            absent=("Mark as Preparing", "Mark as Completed"),
        )

        # HANDED_TO_DELIVERY
        transition_order_status(
            order,
            Order.Status.HANDED_TO_DELIVERY,
        )
        assert_actions_visible(
            "Mark as Completed",
            "Cancel Order",
            absent=("Mark as Preparing", "Hand to Delivery"),
        )

        # COMPLETED
        transition_order_status(order, Order.Status.COMPLETED)
        assert_actions_visible(
            "Order items",
            absent=(
                "Order actions",
                "Mark as Preparing",
                "Hand to Delivery",
                "Mark as Completed",
                "Cancel Order",
            ),
        )

        # CANCELLED
        cancelled_order = self.create_delivery_order(
            customer_phone="03987654",
        )
        cancel_order(cancelled_order, "Customer requested cancellation.")

        cancelled_detail_url = reverse(
            "orders:order-detail",
            args=[self.shop.pk, cancelled_order.pk],
        )
        response = self.client.get(cancelled_detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cancellation reason")
        self.assertNotContains(response, "Order actions")
        self.assertNotContains(response, "Cancel Order")


    def test_all_invalid_status_transitions_are_rejected(self):
        # Multiple orders are created, so provide enough stock for each.
        self.usd_variant.stock_quantity = 100
        self.usd_variant.save(update_fields=["stock_quantity"])
        self.lbp_variant.stock_quantity = 100
        self.lbp_variant.save(update_fields=["stock_quantity"])

        valid_next_status = {
            Order.Status.NEW: Order.Status.PREPARING,
            Order.Status.PREPARING: Order.Status.HANDED_TO_DELIVERY,
            Order.Status.HANDED_TO_DELIVERY: Order.Status.COMPLETED,
        }

        for index, source_status in enumerate(Order.Status):
            order = self.create_delivery_order(
                customer_phone=f"03{index:06d}",
            )

            # Reach each source status through the existing services.
            if source_status == Order.Status.PREPARING:
                transition_order_status(
                    order,
                    Order.Status.PREPARING,
                )
            elif source_status in {
                Order.Status.HANDED_TO_DELIVERY,
                Order.Status.COMPLETED,
            }:
                transition_order_status(
                    order,
                    Order.Status.PREPARING,
                )
                transition_order_status(
                    order,
                    Order.Status.HANDED_TO_DELIVERY,
                )

                if source_status == Order.Status.COMPLETED:
                    transition_order_status(
                        order,
                        Order.Status.COMPLETED,
                    )
            elif source_status == Order.Status.CANCELLED:
                cancel_order(order, "Test cancellation.")

            for target_status in Order.Status:
                if target_status == valid_next_status.get(source_status):
                    continue

                with self.subTest(
                    source=source_status,
                    target=target_status,
                ):
                    with self.assertRaises(ValidationError):
                        transition_order_status(order, target_status)

                    order.refresh_from_db()
                    self.assertEqual(order.status, source_status)

    def test_order_action_returns_404_for_another_owner(self):
        order = self.create_delivery_order()

        other_owner = User.objects.create_user(
            email="other-owner@example.com",
            password="testpass123",
            full_name="Other Shop Owner",
            status=User.Status.ACTIVE,
        )
        self.client.force_login(other_owner)

        response = self.client.post(
            reverse(
                "orders:order-action",
                args=[self.shop.pk, order.pk],
            ),
            {
                "action": "advance",
                "target_status": Order.Status.PREPARING,
            },
        )

        self.assertEqual(response.status_code, 404)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.NEW)


class OrderSuccessViewTests(TestCase):
    """Order-success is now a real page, looked up by the order's own
    tracking_token (never by pk — see the security note in orders/views.py)."""

    def setUp(self):
        self.owner = User.objects.create_user(
            "order-success-owner@example.com", "testpassword123",
            full_name="Order Success Owner", status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        self.shop = Shop.objects.create(
            owner=self.owner, name="Sara's Closet", slug="saras-closet-order-success",
            exchange_rate_lbp_per_usd="89500.00", pickup_available=True,
        )
        Subscription.objects.create(
            shop=self.shop, plan=Subscription.Plan.BASIC,
            status=Subscription.Status.ACTIVE, starts_on=date.today(),
        )
        self.category = Category.objects.create(shop=self.shop, name="Clothing")
        self.product = Product.objects.create(
            shop=self.shop, category=self.category, name="Denim Jacket",
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, color="Indigo", size="M",
            unit_price="45.00", stock_quantity=10,
        )
        self.payment_method = ShopPaymentMethod.objects.create(
            shop=self.shop, method_name=ShopPaymentMethod.MethodName.CASH, enabled=True,
        )

    def _checkout(self, phone="70999888"):
        self.client.post(reverse("cart_add", args=[self.shop.slug]), {
            "variant_id": self.variant.pk, "quantity": 1,
        })
        return self.client.post(reverse("checkout", args=[self.shop.slug]), {
            "customer_name": "John Shopper",
            "customer_phone": phone,
            "fulfillment_type": "PICKUP",
            "selected_payment_method": self.payment_method.pk,
            "currency": "USD",
        })

    def test_real_order_success_shows_actual_submitted_data(self):
        self._checkout()
        order = Order.objects.get()

        response = self.client.get(
            reverse("order_success", args=[self.shop.slug, order.tracking_token])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "John Shopper")
        self.assertContains(response, "Denim Jacket")

    def test_unknown_tracking_token_404s(self):
        response = self.client.get(
            reverse("order_success", args=[self.shop.slug, uuid.uuid4()])
        )

        self.assertEqual(response.status_code, 404)

    def test_order_from_a_different_shop_404s(self):
        self._checkout()
        order = Order.objects.get()

        other_owner = User.objects.create_user(
            "order-success-other-owner@example.com", "testpassword123",
            full_name="Other Owner", status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        other_shop = Shop.objects.create(
            owner=other_owner, name="Other Shop", slug="other-shop-order-success",
            exchange_rate_lbp_per_usd="89500.00",
        )
        Subscription.objects.create(
            shop=other_shop, plan=Subscription.Plan.BASIC,
            status=Subscription.Status.ACTIVE, starts_on=date.today(),
        )

        response = self.client.get(
            reverse("order_success", args=[other_shop.slug, order.tracking_token])
        )

        self.assertEqual(response.status_code, 404)

    def test_success_page_shows_real_payment_method_name(self):
        self._checkout()
        order = Order.objects.get()

        self.assertEqual(_payment_method_display(order), "Cash")

    def test_success_page_falls_back_when_payment_method_missing(self):
        # selected_payment_method is PROTECT + NOT NULL today, so a shop can
        # never actually delete one out from under a placed order — this
        # mutates an in-memory (unsaved) copy to exercise the guard directly.
        self._checkout()
        order = Order.objects.get()
        order.selected_payment_method = None

        self.assertEqual(_payment_method_display(order), "Not available")


class OrderTrackingViewTests(TestCase):
    """The persistent "where's my order" page — same lookup rules as
    order_success (tracking_token + shop, never pk), plus the status/
    cancellation-reason display that's specific to this page."""

    def setUp(self):
        self.owner = User.objects.create_user(
            email="tracking-owner@example.com", password="testpass123",
            full_name="Tracking Owner", status=User.Status.ACTIVE,
        )
        self.shop = Shop.objects.create(
            owner=self.owner, name="Tracking Shop", slug="tracking-shop",
            pickup_available=True, exchange_rate_lbp_per_usd=Decimal("90000.00"),
        )
        Subscription.objects.create(
            shop=self.shop, plan=Subscription.Plan.BASIC,
            status=Subscription.Status.ACTIVE, starts_on=date.today(),
        )
        self.category = Category.objects.create(shop=self.shop, name="Clothing")
        self.product = Product.objects.create(
            shop=self.shop, category=self.category, name="Tracked Hoodie",
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, color="Grey", size="L",
            unit_price=Decimal("25.00"), currency=ProductVariant.Currency.USD,
            stock_quantity=5,
        )
        self.delivery_zone = DeliveryZone.objects.create(
            shop=self.shop, area_name="Jounieh", fee=Decimal("4.00"),
        )
        self.payment_method = ShopPaymentMethod.objects.create(
            shop=self.shop, method_name=ShopPaymentMethod.MethodName.CASH, enabled=True,
        )

    def _place_order(self, **overrides):
        data = {
            "shop": self.shop,
            "customer_name": "Track Customer",
            "customer_phone": "70555000",
            "fulfillment_type": Order.FulfillmentType.DELIVERY,
            "selected_payment_method": self.payment_method,
            "items": [{"variant_id": self.variant.pk, "quantity": 1}],
            "currency": Order.Currency.USD,
            "delivery_zone": self.delivery_zone,
            "address": "Jounieh Highway",
        }
        data.update(overrides)
        return create_order(**data)

    def test_valid_token_shows_the_real_order(self):
        order = self._place_order()

        response = self.client.get(
            reverse("track_order", args=[self.shop.slug, order.tracking_token])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order.order_number)
        self.assertContains(response, "Tracked Hoodie")
        self.assertContains(response, "Track Customer")

    def test_wrong_token_404s(self):
        self._place_order()

        response = self.client.get(
            reverse("track_order", args=[self.shop.slug, uuid.uuid4()])
        )

        self.assertEqual(response.status_code, 404)

    def test_token_under_another_shops_slug_404s(self):
        order = self._place_order()

        other_owner = User.objects.create_user(
            email="tracking-other-owner@example.com", password="testpass123",
            full_name="Other Tracking Owner", status=User.Status.ACTIVE,
        )
        other_shop = Shop.objects.create(
            owner=other_owner, name="Other Tracking Shop", slug="other-tracking-shop",
            exchange_rate_lbp_per_usd="89500.00",
        )
        Subscription.objects.create(
            shop=other_shop, plan=Subscription.Plan.BASIC,
            status=Subscription.Status.ACTIVE, starts_on=date.today(),
        )

        response = self.client.get(
            reverse("track_order", args=[other_shop.slug, order.tracking_token])
        )

        self.assertEqual(response.status_code, 404)

    def test_cancelled_order_shows_its_reason(self):
        order = self._place_order()
        cancel_order(order, "Customer requested a different size.")

        response = self.client.get(
            reverse("track_order", args=[self.shop.slug, order.tracking_token])
        )

        self.assertContains(response, "Cancelled")
        self.assertContains(response, "Customer requested a different size.")

    def test_deactivated_variant_still_renders_via_snapshot(self):
        # The variant can't actually be deleted while this OrderItem
        # references it (on_delete=PROTECT) — deactivating it is the
        # real-world equivalent a merchant can trigger, and the page
        # must still render correctly from the item's own snapshot.
        order = self._place_order()
        self.variant.is_active = False
        self.variant.save(update_fields=["is_active"])

        response = self.client.get(
            reverse("track_order", args=[self.shop.slug, order.tracking_token])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tracked Hoodie")

    def test_deleted_delivery_zone_still_renders_via_snapshot(self):
        order = self._place_order()
        self.delivery_zone.delete()

        response = self.client.get(
            reverse("track_order", args=[self.shop.slug, order.tracking_token])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jounieh")
        self.assertContains(response, "Jounieh Highway")

    def test_no_payment_shows_unpaid_status(self):
        order = self._place_order()

        response = self.client.get(
            reverse("track_order", args=[self.shop.slug, order.tracking_token])
        )

        self.assertContains(response, "Unpaid")

    def test_linked_from_order_success_page(self):
        order = self._place_order()

        response = self.client.get(
            reverse("order_success", args=[self.shop.slug, order.tracking_token])
        )

        self.assertContains(
            response,
            reverse("track_order", args=[self.shop.slug, order.tracking_token]),
        )

    def test_payment_method_missing_shows_not_available(self):
        # Same PROTECT + NOT NULL caveat as above — the DB would reject a
        # real NULL write, so this renders the template directly against
        # an in-memory (unsaved) mutation instead of going through a live
        # GET, which would just re-fetch the real payment method from the DB.
        order = self._place_order()
        order.selected_payment_method = None

        html = render_to_string(
            "storefront/order_tracking.html",
            {"shop": self.shop, "order": order, **_order_context(order)},
        )

        self.assertIn("Not available", html)
