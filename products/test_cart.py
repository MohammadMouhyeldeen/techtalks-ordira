from datetime import date
from decimal import Decimal

from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.models import User
from orders.models import Order, OrderItem
from shops.models import DeliveryZone, Shop, ShopPaymentMethod, Subscription

from . import cart
from .models import Category, Product, ProductVariant


def _make_request():
    request = RequestFactory().get("/")
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    return request


class CartStorageTests(TestCase):
    """Direct products.cart calls — no view layer, no subscription needed."""

    def setUp(self):
        self.owner = User.objects.create_user(
            "cart-owner@example.com",
            "testpassword123",
            full_name="Cart Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Sara's Closet",
            slug="saras-closet-cart",
            exchange_rate_lbp_per_usd="89500.00",
        )
        self.category = Category.objects.create(shop=self.shop, name="Clothing")
        self.product = Product.objects.create(
            shop=self.shop, category=self.category, name="Denim Jacket",
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, color="Indigo", size="M",
            unit_price="45.00", stock_quantity=10,
        )

    def test_add_item_accumulates_on_repeat_add(self):
        request = _make_request()
        cart.add_item(request, self.shop, self.variant, 1)
        cart.add_item(request, self.shop, self.variant, 2)

        lines = cart.get_lines(request, self.shop)

        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["quantity"], 3)

    def test_two_shops_carts_stay_isolated(self):
        other_owner = User.objects.create_user(
            "cart-other-owner@example.com", "testpassword123",
            full_name="Other Owner", status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        other_shop = Shop.objects.create(
            owner=other_owner, name="Other Shop", slug="other-shop-cart",
            exchange_rate_lbp_per_usd="89500.00",
        )
        other_category = Category.objects.create(shop=other_shop, name="Accessories")
        other_product = Product.objects.create(
            shop=other_shop, category=other_category, name="Tote Bag",
        )
        other_variant = ProductVariant.objects.create(
            product=other_product, color="Natural", size="One size",
            unit_price="18.00", stock_quantity=5,
        )

        request = _make_request()
        cart.add_item(request, self.shop, self.variant, 1)
        cart.add_item(request, other_shop, other_variant, 1)

        self.assertEqual(len(cart.get_lines(request, self.shop)), 1)
        self.assertEqual(len(cart.get_lines(request, other_shop)), 1)
        self.assertEqual(
            cart.get_lines(request, self.shop)[0]["variant"], self.variant
        )

    def test_update_item_to_zero_removes_it(self):
        request = _make_request()
        cart.add_item(request, self.shop, self.variant, 2)
        cart.update_item(request, self.shop, self.variant.pk, 0)

        self.assertEqual(cart.get_lines(request, self.shop), [])

    def test_get_lines_excludes_deleted_variant_and_prunes_session(self):
        request = _make_request()
        cart.add_item(request, self.shop, self.variant, 1)
        variant_pk = self.variant.pk
        self.variant.delete()

        self.assertEqual(cart.get_lines(request, self.shop), [])
        # The stale key was pruned, not just filtered — a raw count confirms it.
        self.assertEqual(cart.get_raw_count(request, self.shop), 0)
        self.assertEqual(cart.get_item_count(request, self.shop), 0)

    def test_get_lines_excludes_deactivated_variant(self):
        request = _make_request()
        cart.add_item(request, self.shop, self.variant, 1)
        self.variant.is_active = False
        self.variant.save()

        self.assertEqual(cart.get_lines(request, self.shop), [])

    def test_get_lines_excludes_variant_from_wrong_shop(self):
        other_owner = User.objects.create_user(
            "cart-wrong-shop-owner@example.com", "testpassword123",
            full_name="Wrong Shop Owner", status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        other_shop = Shop.objects.create(
            owner=other_owner, name="Wrong Shop", slug="wrong-shop-cart",
            exchange_rate_lbp_per_usd="89500.00",
        )

        request = _make_request()
        # Directly construct the session's documented shape — simulates a
        # stale/foreign variant id ending up under the wrong shop bucket.
        request.session["cart"] = {str(other_shop.pk): {str(self.variant.pk): 1}}
        request.session.modified = True

        self.assertEqual(cart.get_lines(request, other_shop), [])

    def test_get_totals_keeps_usd_and_lbp_separate(self):
        lbp_variant = ProductVariant.objects.create(
            product=self.product, color="Indigo", size="L",
            unit_price="4000000.00", currency=ProductVariant.Currency.LBP,
            stock_quantity=5,
        )
        request = _make_request()
        cart.add_item(request, self.shop, self.variant, 1)
        cart.add_item(request, self.shop, lbp_variant, 1)

        totals = cart.get_totals(request, self.shop)

        self.assertEqual(totals["USD"], Decimal("45.00"))
        self.assertEqual(totals["LBP"], Decimal("4000000.00"))

    def test_add_item_clamps_quantity_to_stock(self):
        request = _make_request()
        cart.add_item(request, self.shop, self.variant, 999)

        lines = cart.get_lines(request, self.shop)

        self.assertEqual(lines[0]["quantity"], self.variant.stock_quantity)

    def test_add_item_accumulation_also_clamps_to_stock(self):
        request = _make_request()
        cart.add_item(request, self.shop, self.variant, 7)
        cart.add_item(request, self.shop, self.variant, 7)

        lines = cart.get_lines(request, self.shop)

        self.assertEqual(lines[0]["quantity"], self.variant.stock_quantity)

    def test_add_item_with_zero_stock_adds_nothing(self):
        out_of_stock = ProductVariant.objects.create(
            product=self.product, color="Indigo", size="S",
            unit_price="45.00", stock_quantity=0,
        )
        request = _make_request()
        cart.add_item(request, self.shop, out_of_stock, 1)

        self.assertEqual(cart.get_lines(request, self.shop), [])

    def test_update_item_ignores_key_not_already_present(self):
        """update_item must never plant a new entry — only modify one
        that add_item already created. This is what stops a malformed
        or unresolved variant_id from poisoning the session."""
        request = _make_request()
        cart.update_item(request, self.shop, 999999, 3)

        self.assertEqual(cart.get_lines(request, self.shop), [])
        self.assertEqual(cart.get_raw_count(request, self.shop), 0)

    def test_read_only_helpers_do_not_create_a_session_bucket(self):
        request = _make_request()
        # _make_request()'s own forced session.save() flips `modified`
        # (Django's db backend sets it when it creates the session row) —
        # that's a harness artifact, not something under test. Clear it
        # so the assertion below measures only what our own calls do.
        request.session.modified = False

        cart.get_lines(request, self.shop)
        cart.get_item_count(request, self.shop)
        cart.get_totals(request, self.shop)
        cart.get_raw_count(request, self.shop)
        cart.update_item(request, self.shop, self.variant.pk, 5)
        cart.remove_item(request, self.shop, self.variant.pk)

        self.assertNotIn(cart.SESSION_KEY, request.session)
        self.assertFalse(request.session.modified)


class CartViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "cart-view-owner@example.com", "testpassword123",
            full_name="Cart View Owner", status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        self.shop = Shop.objects.create(
            owner=self.owner, name="Sara's Closet", slug="saras-closet-cart-view",
            exchange_rate_lbp_per_usd="89500.00",
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
        self.cart_url = reverse("cart_view", args=[self.shop.slug])
        self.add_url = reverse("cart_add", args=[self.shop.slug])
        self.update_url = reverse("cart_update", args=[self.shop.slug])
        self.remove_url = reverse("cart_remove", args=[self.shop.slug])

    def test_valid_add_shows_on_cart_view(self):
        self.client.post(self.add_url, {"variant_id": self.variant.pk, "quantity": 2})

        response = self.client.get(self.cart_url)

        self.assertContains(response, "Denim Jacket")
        self.assertContains(response, "90.00")

    def test_get_on_cart_add_is_not_allowed(self):
        response = self.client.get(self.add_url)

        self.assertEqual(response.status_code, 405)

    def test_adding_variant_from_different_shop_is_rejected(self):
        other_owner = User.objects.create_user(
            "cart-view-other-owner@example.com", "testpassword123",
            full_name="Other Owner", status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        other_shop = Shop.objects.create(
            owner=other_owner, name="Other Shop", slug="other-shop-cart-view",
            exchange_rate_lbp_per_usd="89500.00",
        )
        Subscription.objects.create(
            shop=other_shop, plan=Subscription.Plan.BASIC,
            status=Subscription.Status.ACTIVE, starts_on=date.today(),
        )

        other_add_url = reverse("cart_add", args=[other_shop.slug])
        self.client.post(other_add_url, {"variant_id": self.variant.pk, "quantity": 1})

        response = self.client.get(reverse("cart_view", args=[other_shop.slug]))

        self.assertNotContains(response, "Denim Jacket")

    def test_update_reflected_on_next_get(self):
        self.client.post(self.add_url, {"variant_id": self.variant.pk, "quantity": 1})
        update_url = reverse("cart_update", args=[self.shop.slug])
        self.client.post(update_url, {"variant_id": self.variant.pk, "quantity": 5})

        response = self.client.get(self.cart_url)

        self.assertContains(response, "225.00")

    def test_remove_reflected_on_next_get(self):
        self.client.post(self.add_url, {"variant_id": self.variant.pk, "quantity": 1})
        remove_url = reverse("cart_remove", args=[self.shop.slug])
        self.client.post(remove_url, {"variant_id": self.variant.pk})

        response = self.client.get(self.cart_url)

        self.assertContains(response, "Your cart is empty")

    def test_empty_cart_renders_empty_state(self):
        response = self.client.get(self.cart_url)

        self.assertContains(response, "Your cart is empty")

    def test_add_out_of_stock_variant_is_rejected(self):
        out_of_stock = ProductVariant.objects.create(
            product=self.product, color="Indigo", size="L",
            unit_price="45.00", stock_quantity=0,
        )

        self.client.post(self.add_url, {"variant_id": out_of_stock.pk, "quantity": 1})
        response = self.client.get(self.cart_url)

        self.assertContains(response, "Your cart is empty")

    def test_add_quantity_is_clamped_to_stock(self):
        self.client.post(self.add_url, {"variant_id": self.variant.pk, "quantity": 999})

        response = self.client.get(self.cart_url)

        # 10 in stock x $45.00 = $450.00, never 999 x $45.00.
        self.assertContains(response, "450.00")

    def test_update_quantity_is_clamped_to_stock(self):
        self.client.post(self.add_url, {"variant_id": self.variant.pk, "quantity": 1})
        self.client.post(self.update_url, {"variant_id": self.variant.pk, "quantity": 999})

        response = self.client.get(self.cart_url)

        self.assertContains(response, "450.00")

    def test_malformed_variant_id_on_add_does_not_500(self):
        response = self.client.post(self.add_url, {"variant_id": "abc", "quantity": 1})

        self.assertNotEqual(response.status_code, 500)

    def test_malformed_variant_id_on_update_does_not_500(self):
        response = self.client.post(self.update_url, {"variant_id": "abc", "quantity": 1})

        self.assertNotEqual(response.status_code, 500)

    def test_malformed_variant_id_on_remove_does_not_500(self):
        response = self.client.post(self.remove_url, {"variant_id": "abc"})

        self.assertNotEqual(response.status_code, 500)

    def test_malformed_variant_id_on_update_does_not_poison_session(self):
        self.client.post(self.add_url, {"variant_id": self.variant.pk, "quantity": 1})
        self.client.post(self.update_url, {"variant_id": "abc", "quantity": 5})

        response = self.client.get(self.cart_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Denim Jacket")


class CartSessionHygieneTests(TestCase):
    """A visitor who never touches the cart must never get a session
    cookie written just for loading a page — storefront_cart's own read
    (cart_count in the navbar) must not force-create one either."""

    def setUp(self):
        self.owner = User.objects.create_user(
            "cart-hygiene-owner@example.com", "testpassword123",
            full_name="Hygiene Owner", status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        self.shop = Shop.objects.create(
            owner=self.owner, name="Sara's Closet", slug="saras-closet-hygiene",
            exchange_rate_lbp_per_usd="89500.00",
        )
        Subscription.objects.create(
            shop=self.shop, plan=Subscription.Plan.BASIC,
            status=Subscription.Status.ACTIVE, starts_on=date.today(),
        )
        self.category = Category.objects.create(shop=self.shop, name="Clothing")
        self.product = Product.objects.create(
            shop=self.shop, category=self.category, name="Denim Jacket",
        )
        ProductVariant.objects.create(
            product=self.product, color="Indigo", size="M",
            unit_price="45.00", stock_quantity=10,
        )

    def test_catalog_view_creates_no_session_cookie(self):
        response = self.client.get(reverse("public_catalog", args=[self.shop.slug]))

        self.assertNotIn("sessionid", response.cookies)

    def test_product_detail_view_creates_no_session_cookie(self):
        response = self.client.get(
            reverse("product_detail", args=[self.shop.slug, self.product.pk])
        )

        self.assertNotIn("sessionid", response.cookies)

    def test_empty_cart_view_creates_no_session_cookie(self):
        response = self.client.get(reverse("cart_view", args=[self.shop.slug]))

        self.assertNotIn("sessionid", response.cookies)


class CheckoutViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "checkout-owner@example.com", "testpassword123",
            full_name="Checkout Owner", status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        self.shop = Shop.objects.create(
            owner=self.owner, name="Sara's Closet", slug="saras-closet-checkout",
            exchange_rate_lbp_per_usd="89500.00", pickup_available=False,
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
        self.active_zone = DeliveryZone.objects.create(
            shop=self.shop, area_name="Beirut", fee="3.00",
        )
        self.inactive_zone = DeliveryZone.objects.create(
            shop=self.shop, area_name="Tripoli", fee="5.00", is_active=False,
        )
        self.payment_method = ShopPaymentMethod.objects.create(
            shop=self.shop, method_name=ShopPaymentMethod.MethodName.CASH, enabled=True,
        )
        self.disabled_method = ShopPaymentMethod.objects.create(
            shop=self.shop, method_name=ShopPaymentMethod.MethodName.WHISH, enabled=False,
        )

        self.checkout_url = reverse("checkout", args=[self.shop.slug])
        self.add_url = reverse("cart_add", args=[self.shop.slug])

    def _add_to_cart(self):
        self.client.post(self.add_url, {"variant_id": self.variant.pk, "quantity": 1})

    def _valid_post_data(self, **overrides):
        data = {
            "customer_name": "Jane Doe",
            "customer_phone": "70123456",
            "fulfillment_type": "DELIVERY",
            "delivery_zone": self.active_zone.pk,
            "address": "Hamra Street",
            "selected_payment_method": self.payment_method.pk,
            "currency": "USD",
        }
        data.update(overrides)
        return data

    def test_empty_cart_redirects_to_cart_view_without_rendering_form(self):
        response = self.client.get(self.checkout_url)

        self.assertRedirects(response, reverse("cart_view", args=[self.shop.slug]))

    def test_only_active_zones_and_enabled_payment_methods_listed(self):
        self._add_to_cart()

        response = self.client.get(self.checkout_url)

        self.assertContains(response, "Beirut")
        self.assertNotContains(response, "Tripoli")
        self.assertContains(response, "Cash")
        self.assertNotContains(response, "Whish")

    def test_pickup_option_absent_when_shop_disallows_it(self):
        self._add_to_cart()

        response = self.client.get(self.checkout_url)

        self.assertNotContains(response, 'value="PICKUP"')

    def test_pickup_option_present_when_shop_allows_it(self):
        self.shop.pickup_available = True
        self.shop.save()
        self._add_to_cart()

        response = self.client.get(self.checkout_url)

        self.assertContains(response, 'value="PICKUP"')

    def test_valid_post_creates_zero_order_rows_and_redirects(self):
        self._add_to_cart()

        response = self.client.post(self.checkout_url, self._valid_post_data())

        self.assertRedirects(response, reverse("order_success", args=[self.shop.slug]))
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)

    def test_valid_post_leaves_cart_untouched(self):
        self._add_to_cart()
        self.client.post(self.checkout_url, self._valid_post_data())

        response = self.client.get(reverse("cart_view", args=[self.shop.slug]))

        self.assertContains(response, "Denim Jacket")

    def test_missing_zone_and_address_for_delivery_rerenders_with_errors(self):
        self._add_to_cart()

        response = self.client.post(self.checkout_url, self._valid_post_data(
            delivery_zone="", address="",
        ))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a delivery area.")
        self.assertContains(response, "Enter a delivery address.")
