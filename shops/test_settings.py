from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from products.models import Category, Product, ProductVariant

from .models import Shop


class ShopSettingsViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "settings-owner@example.com",
            "testpassword123",
            full_name="Settings Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Sara's Closet",
            slug="saras-closet-settings",
            whatsapp="96170123456",
            instagram="@sarascloset",
            exchange_rate_lbp_per_usd="89500.00",
        )
        self.settings_url = reverse("shops:settings")

    def test_unauthenticated_user_is_redirected_to_login(self):
        response = self.client.get(self.settings_url)

        self.assertNotEqual(response.status_code, 200)

    def test_owner_without_shop_is_redirected_to_setup(self):
        ownerless = User.objects.create_user(
            "no-shop-owner@example.com",
            "testpassword123",
            full_name="No Shop Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        self.client.force_login(ownerless)

        response = self.client.get(self.settings_url)

        self.assertRedirects(response, reverse("shops:setup"))

    def test_get_prefills_form_with_current_shop_data(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.settings_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].instance, self.shop)
        self.assertContains(response, "Sara&#x27;s Closet")
        self.assertContains(response, "@sarascloset")

    def test_owner_can_edit_and_save_shop_settings(self):
        self.client.force_login(self.owner)

        response = self.client.post(self.settings_url, {
            "name": "Sara's Boutique",
            "whatsapp": "96170123456",
            "instagram": "@sarasboutique",
            "pickup_available": "on",
        })

        self.assertRedirects(response, self.settings_url)

        self.shop.refresh_from_db()
        self.assertEqual(self.shop.name, "Sara's Boutique")
        self.assertEqual(self.shop.instagram, "@sarasboutique")
        self.assertTrue(self.shop.pickup_available)

    def test_changes_are_reflected_immediately_on_next_get(self):
        self.client.force_login(self.owner)

        self.client.post(self.settings_url, {
            "name": "Sara's Boutique",
            "whatsapp": "96170123456",
            "instagram": "@sarasboutique",
        })

        response = self.client.get(self.settings_url)

        self.assertContains(response, "Sara&#x27;s Boutique")

    def test_success_message_is_shown_after_save(self):
        self.client.force_login(self.owner)

        response = self.client.post(self.settings_url, {
            "name": "Sara's Boutique",
            "whatsapp": "96170123456",
            "instagram": "@sarasboutique",
        }, follow=True)

        self.assertContains(response, "Shop settings updated.")

    def test_slug_is_not_editable_through_this_form(self):
        self.client.force_login(self.owner)
        original_slug = self.shop.slug

        self.client.post(self.settings_url, {
            "name": "Sara's Boutique",
            "whatsapp": "96170123456",
            "instagram": "@sarasboutique",
            "slug": "hacked-slug",
        })

        self.shop.refresh_from_db()
        self.assertEqual(self.shop.slug, original_slug)

    def test_invalid_whatsapp_is_rejected_and_shop_unchanged(self):
        self.client.force_login(self.owner)

        response = self.client.post(self.settings_url, {
            "name": "Sara's Boutique",
            "whatsapp": "123",
            "instagram": "@sarasboutique",
        })

        self.assertEqual(response.status_code, 200)
        self.shop.refresh_from_db()
        self.assertEqual(self.shop.name, "Sara's Closet")

    def test_no_warehouse_or_card_payment_ui(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.settings_url)

        self.assertNotContains(response, "Warehouse")
        self.assertNotContains(response, "Card")


class ShopSettingsOwnerIsolationTests(TestCase):
    def setUp(self):
        self.owner_a = User.objects.create_user(
            "owner-a@example.com",
            "testpassword123",
            full_name="Owner A",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        self.shop_a = Shop.objects.create(
            owner=self.owner_a,
            name="Shop A",
            slug="shop-a-isolation",
            exchange_rate_lbp_per_usd="89500.00",
        )

        self.owner_b = User.objects.create_user(
            "owner-b@example.com",
            "testpassword123",
            full_name="Owner B",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        self.shop_b = Shop.objects.create(
            owner=self.owner_b,
            name="Shop B",
            slug="shop-b-isolation",
            exchange_rate_lbp_per_usd="89500.00",
        )

        self.settings_url = reverse("shops:settings")

    def test_owner_b_get_never_shows_owner_a_data(self):
        self.client.force_login(self.owner_b)

        response = self.client.get(self.settings_url)

        self.assertContains(response, "Shop B")
        self.assertNotContains(response, "Shop A")

    def test_owner_b_post_only_mutates_owner_b_shop(self):
        self.client.force_login(self.owner_b)

        self.client.post(self.settings_url, {
            "name": "Shop B Renamed",
            "whatsapp": "",
            "instagram": "",
        })

        self.shop_b.refresh_from_db()
        self.shop_a.refresh_from_db()

        self.assertEqual(self.shop_b.name, "Shop B Renamed")
        self.assertEqual(self.shop_a.name, "Shop A")


class DashboardStatsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "dashboard-owner@example.com",
            "testpassword123",
            full_name="Dashboard Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Stats Shop",
            slug="stats-shop",
            exchange_rate_lbp_per_usd="89500.00",
        )
        self.category = Category.objects.create(shop=self.shop, name="Clothing")

        active_product = Product.objects.create(
            shop=self.shop, category=self.category, name="Active Shirt",
        )
        ProductVariant.objects.create(
            product=active_product, color="Blue", size="S",
            unit_price="20.00", stock_quantity=1, low_stock_threshold=2,
        )
        ProductVariant.objects.create(
            product=active_product, color="Blue", size="M",
            unit_price="20.00", stock_quantity=10, low_stock_threshold=2,
        )

        inactive_product = Product.objects.create(
            shop=self.shop, category=self.category, name="Archived Jacket",
            is_active=False,
        )
        ProductVariant.objects.create(
            product=inactive_product, color="Black", size="M",
            unit_price="40.00", stock_quantity=0, low_stock_threshold=2,
        )

        self.dashboard_url = reverse("shops:dashboard")

    def test_dashboard_shows_real_counts_matching_the_database(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.context["total_products"], 1)
        self.assertEqual(response.context["total_variants"], 2)
        self.assertEqual(response.context["low_stock_count"], 1)

    def test_dashboard_counts_exclude_other_shops(self):
        other_owner = User.objects.create_user(
            "other-dashboard-owner@example.com",
            "testpassword123",
            full_name="Other Dashboard Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        other_shop = Shop.objects.create(
            owner=other_owner,
            name="Other Stats Shop",
            slug="other-stats-shop",
            exchange_rate_lbp_per_usd="89500.00",
        )
        other_category = Category.objects.create(shop=other_shop, name="Accessories")
        other_product = Product.objects.create(
            shop=other_shop, category=other_category, name="Other Shop Product",
        )
        ProductVariant.objects.create(
            product=other_product, color="Red", size="M",
            unit_price="15.00", stock_quantity=5, low_stock_threshold=2,
        )

        self.client.force_login(self.owner)
        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.context["total_products"], 1)
        self.assertEqual(response.context["total_variants"], 2)

    def test_no_warehouse_or_card_payment_ui(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.dashboard_url)

        self.assertNotContains(response, "Warehouse")
        self.assertNotContains(response, "Card")
