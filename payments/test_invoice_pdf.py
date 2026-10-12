from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer
from orders.models import Order, OrderItem
from products.models import Category, Product, ProductVariant
from shops.models import Shop, ShopPaymentMethod

from .models import Invoice


User = get_user_model()


class InvoicePDFTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="invoice-owner@example.com",
            password="testpass123",
            full_name="Invoice Owner",
            status=User.Status.ACTIVE,
        )

        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Invoice Shop",
            slug="invoice-shop",
            whatsapp="96170123456",
            pickup_available=True,
            exchange_rate_lbp_per_usd=Decimal("90000.00"),
        )

        self.customer = Customer.objects.create(
            shop=self.shop,
            full_name="Invoice Customer",
            phone_number="70123456",
        )

        self.payment_method = ShopPaymentMethod.objects.create(
            shop=self.shop,
            method_name=ShopPaymentMethod.MethodName.CASH,
            enabled=True,
        )

        self.order = Order.objects.create(
            shop=self.shop,
            customer=self.customer,
            selected_payment_method=self.payment_method,
            order_number="ORD-INVOICE-TEST",
            fulfillment_type=Order.FulfillmentType.PICKUP,
            status=Order.Status.NEW,
            customer_name_snapshot="Invoice Customer",
            customer_phone_snapshot="70123456",
            zone_name_snapshot="",
            delivery_fee_snapshot=Decimal("0.00"),
            address_snapshot="",
            items_total=Decimal("15.00"),
            total=Decimal("15.00"),
            currency=Order.Currency.USD,
            fx_rate_snapshot=Decimal("90000.00"),
        )

        self.category = Category.objects.create(
            shop=self.shop,
            name="Invoice Category",
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
            unit_price=Decimal("15.00"),
            currency=ProductVariant.Currency.USD,
            stock_quantity=5,
            low_stock_threshold=1,
        )

        self.order_item = OrderItem.objects.create(
            order=self.order,
            variant=self.variant,
            product_name_snapshot="Classic T-shirt",
            color_snapshot="Black",
            size_snapshot="Medium",
            unit_price_snapshot=Decimal("15.00"),
            quantity=1,
            line_total=Decimal("15.00"),
        )

        self.invoice_url = reverse(
            "orders:invoice-pdf",
            kwargs={
                "shop_pk": self.shop.pk,
                "order_pk": self.order.pk,
            },
        )

    def test_owner_can_download_invoice_pdf(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.invoice_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/pdf",
        )
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertIn(
            'attachment; filename="INV-',
            response["Content-Disposition"],
        )

        invoice = Invoice.objects.get(order=self.order)

        self.assertEqual(invoice.shop, self.shop)
        self.assertEqual(invoice.status, Invoice.Status.ISSUED)
        self.assertIsNotNone(invoice.issued_at)
        self.assertEqual(
            invoice.subtotal_snapshot,
            Decimal("15.00"),
        )
        self.assertEqual(
            invoice.delivery_fee_snapshot,
            Decimal("0.00"),
        )
        self.assertEqual(
            invoice.total_snapshot,
            Decimal("15.00"),
        )
        self.assertEqual(invoice.currency, Order.Currency.USD)

    def test_repeated_download_uses_same_invoice_number(self):
        self.client.force_login(self.owner)

        first_response = self.client.get(self.invoice_url)
        first_invoice = Invoice.objects.get(order=self.order)
        first_number = first_invoice.invoice_number

        second_response = self.client.get(self.invoice_url)
        second_invoice = Invoice.objects.get(order=self.order)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(
            second_invoice.invoice_number,
            first_number,
        )
        self.assertEqual(
            Invoice.objects.filter(order=self.order).count(),
            1,
        )

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(self.invoice_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)
        self.assertIn("next=", response.url)

    def test_other_shop_owner_receives_404(self):
        other_owner = User.objects.create_user(
            email="other-invoice-owner@example.com",
            password="testpass123",
            full_name="Other Invoice Owner",
            status=User.Status.ACTIVE,
        )

        other_shop = Shop.objects.create(
            owner=other_owner,
            name="Other Invoice Shop",
            slug="other-invoice-shop",
            whatsapp="96170999999",
            pickup_available=True,
            exchange_rate_lbp_per_usd=Decimal("90000.00"),
        )

        self.client.force_login(self.owner)

        cross_shop_url = reverse(
            "orders:invoice-pdf",
            kwargs={
                "shop_pk": other_shop.pk,
                "order_pk": self.order.pk,
            },
        )

        response = self.client.get(cross_shop_url)

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            Invoice.objects.filter(order=self.order).exists()
        )

    def test_invoice_works_after_variant_is_deleted(self):
        self.variant.delete()
        self.order_item.refresh_from_db()

        self.assertIsNone(self.order_item.variant)

        self.client.force_login(self.owner)

        response = self.client.get(self.invoice_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/pdf",
        )
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertTrue(
            Invoice.objects.filter(order=self.order).exists()
        )

    def test_invoice_handles_long_names_and_many_items(self):
        long_product_name = (
            "Extra long product name used to verify that invoice "
            "content wraps correctly without breaking the PDF layout"
        )

        for number in range(30):
            OrderItem.objects.create(
                order=self.order,
                variant=None,
                product_name_snapshot=(
                    f"{long_product_name} {number + 1}"
                ),
                color_snapshot="Very Long Color Description",
                size_snapshot="Extra Large",
                unit_price_snapshot=Decimal("1.00"),
                quantity=1,
                line_total=Decimal("1.00"),
            )

        self.client.force_login(self.owner)

        response = self.client.get(self.invoice_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/pdf",
        )
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertGreater(len(response.content), 1000)