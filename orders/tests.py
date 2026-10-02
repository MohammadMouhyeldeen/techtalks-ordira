from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from customers.models import Customer
from products.models import (
    Category,
    Product,
    ProductVariant,
    StockMovement,
)
from shops.models import DeliveryZone, Shop, ShopPaymentMethod

from .models import Order, OrderItem
from .services import create_order


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