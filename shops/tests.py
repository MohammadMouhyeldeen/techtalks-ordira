
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from accounts.models import User
from .models import Shop, Subscription, DeliveryZone

from datetime import date, timedelta

from .helpers import is_catalog_public, get_latest_subscription, subscription_status


class ShopSetupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "shopowner@example.com",
            "testpassword123",
            full_name="Test Shop Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )

        self.setup_url = reverse("shops:setup")

    def test_unauthenticated_user_is_redirected_to_login(self):
        response = self.client.get(self.setup_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("accounts:login"),
            response.url,
        )

    def test_authenticated_shop_owner_can_open_setup_page(self):
        self.client.force_login(self.user)

        response = self.client.get(self.setup_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "shops/shop_setup.html",
        )

    def test_shop_is_created_with_logged_in_user_as_owner(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.setup_url,
            {
                "name": "Test Fashion",
                "slug": "test-fashion",
                "whatsapp": "+96170123456",
                "instagram": "@testfashion",
                "exchange_rate_lbp_per_usd": "89500.00",
                "pickup_available": "on",
            },
        )

        self.assertRedirects(
            response,
            reverse("shops:dashboard"),
        )

        shop = Shop.objects.get(slug="test-fashion")

        self.assertEqual(shop.owner, self.user)
        self.assertEqual(shop.name, "Test Fashion")
        self.assertEqual(shop.whatsapp, "96170123456")
        self.assertEqual(shop.instagram, "@testfashion")
        self.assertTrue(shop.pickup_available)
        self.assertEqual(
            str(shop.exchange_rate_lbp_per_usd),
            "89500.00",
        )

    def test_duplicate_slug_is_rejected(self):
        self.client.force_login(self.user)

        other_user = User.objects.create_user(
            "otherowner@example.com",
            "testpassword123",
            full_name="Other Shop Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )

        Shop.objects.create(
            owner=other_user,
            name="Existing Shop",
            slug="existing-shop",
            exchange_rate_lbp_per_usd="89500.00",
        )

        response = self.client.post(
            self.setup_url,
            {
                "name": "Another Shop",
                "slug": "existing-shop",
                "whatsapp": "",
                "instagram": "",
                "exchange_rate_lbp_per_usd": "89500.00",
                "pickup_available": "",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            Shop.objects.filter(slug="existing-shop").count(),
            1,
        )

        self.assertContains(
            response,
            "A shop with this URL already exists.",
        )

    def test_invalid_exchange_rate_is_rejected(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.setup_url,
            {
                "name": "Invalid Rate Shop",
                "slug": "invalid-rate-shop",
                "whatsapp": "",
                "instagram": "",
                "exchange_rate_lbp_per_usd": "0",
                "pickup_available": "",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertFalse(
            Shop.objects.filter(
                slug="invalid-rate-shop"
            ).exists()
        )


class ShopSetupReviewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "reviewowner@example.com",
            "testpassword123",
            full_name="Review Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )

        self.admin = User.objects.create_user(
            "reviewadmin@example.com",
            "testpassword123",
            full_name="Review Admin",
            status=User.Status.ACTIVE,
            role=User.Role.ADMIN,
        )

        self.setup_url = reverse("shops:setup")
        self.dashboard_url = reverse("shops:dashboard")

    def test_admin_cannot_use_shop_setup(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.setup_url)

        self.assertRedirects(
            response,
            reverse("accounts:admin_dashboard"),
        )

    def test_admin_cannot_create_shop_from_setup(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            self.setup_url,
            {
                "name": "Admin Shop",
                "slug": "admin-shop",
                "whatsapp": "",
                "instagram": "",
                "exchange_rate_lbp_per_usd": "89500.00",
                "pickup_available": "",
            },
        )

        self.assertRedirects(
            response,
            reverse("accounts:admin_dashboard"),
        )

        self.assertFalse(
            Shop.objects.filter(
                slug="admin-shop"
            ).exists()
        )

    def test_owner_with_shop_is_redirected_from_setup_on_get(self):
        self.client.force_login(self.owner)

        Shop.objects.create(
            owner=self.owner,
            name="Existing Shop",
            slug="existing-shop",
            exchange_rate_lbp_per_usd="89500.00",
        )

        response = self.client.get(self.setup_url)

        self.assertRedirects(
            response,
            self.dashboard_url,
        )

    def test_owner_with_shop_is_redirected_from_setup_on_post(self):
        self.client.force_login(self.owner)

        Shop.objects.create(
            owner=self.owner,
            name="Existing Shop",
            slug="existing-shop",
            exchange_rate_lbp_per_usd="89500.00",
        )

        response = self.client.post(
            self.setup_url,
            {
                "name": "Second Shop",
                "slug": "second-shop",
                "whatsapp": "",
                "instagram": "",
                "exchange_rate_lbp_per_usd": "89500.00",
                "pickup_available": "",
            },
        )

        self.assertRedirects(
            response,
            self.dashboard_url,
        )

        self.assertFalse(
            Shop.objects.filter(
                slug="second-shop"
            ).exists()
        )

    def test_owner_without_shop_is_redirected_from_dashboard_to_setup(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.dashboard_url)

        self.assertRedirects(
            response,
            self.setup_url,
        )

    def test_owner_with_shop_stays_on_dashboard(self):
        self.client.force_login(self.owner)

        Shop.objects.create(
            owner=self.owner,
            name="Existing Shop",
            slug="existing-shop",
            exchange_rate_lbp_per_usd="89500.00",
        )

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "shops/dashboard.html",
        )

    def test_dashboard_renders_shell_template_includes(self):
        """
        Verify that dashboard extends base.html and the shell (base.html)
        actually renders its includes (navbar, sidebar) — not just that
        the view resolves.
        """
        self.client.force_login(self.owner)

        Shop.objects.create(
            owner=self.owner,
            name="Existing Shop",
            slug="existing-shop",
            exchange_rate_lbp_per_usd="89500.00",
        )

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        # Shell-specific markup that would only appear if base.html rendered
        self.assertContains(response, 'class="navbar"')
        self.assertContains(response, 'class="sidebar"')
        # Unique text from sidebar.html
        self.assertContains(response, "Shop Settings")

    def test_admin_stays_on_dashboard(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "shops/dashboard.html",
        )

    def test_slug_is_lowercased(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.setup_url,
            {
                "name": "Luna Fashion",
                "slug": "Luna-Fashion",
                "whatsapp": "",
                "instagram": "",
                "exchange_rate_lbp_per_usd": "89500.00",
                "pickup_available": "",
            },
        )

        self.assertRedirects(
            response,
            self.dashboard_url,
        )

        shop = Shop.objects.get(
            name="Luna Fashion"
        )

        self.assertEqual(
            shop.slug,
            "luna-fashion",
        )

    def test_slug_uniqueness_is_case_insensitive(self):
        self.client.force_login(self.owner)

        other_user = User.objects.create_user(
            "slugowner@example.com",
            "testpassword123",
            full_name="Slug Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )

        Shop.objects.create(
            owner=other_user,
            name="Luna",
            slug="luna",
            exchange_rate_lbp_per_usd="89500.00",
        )

        response = self.client.post(
            self.setup_url,
            {
                "name": "Another Luna",
                "slug": "LUNA",
                "whatsapp": "",
                "instagram": "",
                "exchange_rate_lbp_per_usd": "89500.00",
                "pickup_available": "",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "A shop with this URL already exists.",
        )

        self.assertFalse(
            Shop.objects.filter(
                owner=self.owner,
            ).exists()
        )

    def test_whatsapp_is_normalized(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.setup_url,
            {
                "name": "WhatsApp Shop",
                "slug": "whatsapp-shop",
                "whatsapp": "+961 70-123-(456)",
                "instagram": "",
                "exchange_rate_lbp_per_usd": "89500.00",
                "pickup_available": "",
            },
        )

        self.assertRedirects(
            response,
            self.dashboard_url,
        )

        shop = Shop.objects.get(
            slug="whatsapp-shop"
        )

        self.assertEqual(
            shop.whatsapp,
            "96170123456",
        )

    def test_invalid_whatsapp_is_rejected(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.setup_url,
            {
                "name": "Invalid WhatsApp Shop",
                "slug": "invalid-whatsapp-shop",
                "whatsapp": "hello world",
                "instagram": "",
                "exchange_rate_lbp_per_usd": "89500.00",
                "pickup_available": "",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "Enter a WhatsApp number with 10 to 15 digits",
        )

        self.assertFalse(
            Shop.objects.filter(
                slug="invalid-whatsapp-shop"
            ).exists()
        )

    def test_arabic_indic_whatsapp_is_rejected(self):

        self.client.force_login(self.owner)

        response = self.client.post(
            self.setup_url,{
                "name": "Arabic Indic WhatsApp Shop",
                "slug": "arabic-indic-whatsapp-shop",
                "whatsapp": "٩٦١٧٠١٢٣٤٥٦",
                "instagram": "",
                "exchange_rate_lbp_per_usd": "89500.00",
                "pickup_available": "",
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Enter a WhatsApp number with 10 to 15 digits",
        )
        self.assertFalse(
            Shop.objects.filter(
                slug="arabic-indic-whatsapp-shop"
            ).exists()
        )

    def test_logo_over_2_mb_is_rejected(self):
        self.client.force_login(self.owner)

        image_data = BytesIO()

        image = Image.effect_noise(
            (2200, 2200),
            100,
        ).convert("RGB")

        image.save(
            image_data,
            format="JPEG",
            quality=100,
        )

        image_data.seek(0)

        self.assertGreater(
            len(image_data.getvalue()),
            2 * 1024 * 1024,
        )

        large_logo = SimpleUploadedFile(
            "large-logo.jpg",
            image_data.getvalue(),
            content_type="image/jpeg",
        )

        response = self.client.post(
            self.setup_url,
            {
                "name": "Large Logo Shop",
                "slug": "large-logo-shop",
                "whatsapp": "",
                "instagram": "",
                "logo": large_logo,
                "exchange_rate_lbp_per_usd": "89500.00",
                "pickup_available": "",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "Logo must be 2 MB or smaller.",
        )

        self.assertFalse(
            Shop.objects.filter(
                slug="large-logo-shop"
            ).exists()
        )


class SidebarCatalogSectionTests(TestCase):
    """Explicit tests for the {% if shop %} guard on the Catalog sidebar
    section. Prevents the NoReverseMatch regression where shopless users
    hit a 500 on any base.html-rendering page."""

    def setUp(self):
        self.owner = User.objects.create_user(
            "sidebar-owner@example.com",
            "testpassword123",
            full_name="Sidebar Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        self.admin = User.objects.create_user(
            "sidebar-admin@example.com",
            "testpassword123",
            full_name="Sidebar Admin",
            status=User.Status.ACTIVE,
            role=User.Role.ADMIN,
        )
        self.dashboard_url = reverse("shops:dashboard")

    def _create_shop_for(self, owner):
        return Shop.objects.create(
            owner=owner,
            name="Sidebar Shop",
            slug="sidebar-shop",
            exchange_rate_lbp_per_usd="89500.00",
        )

    def test_catalog_section_shows_for_owner_with_shop(self):
        self._create_shop_for(self.owner)
        self.client.force_login(self.owner)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Catalog")
        self.assertContains(response, "Products")

    def test_catalog_section_hidden_for_admin_without_shop(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Catalog")
        self.assertNotContains(response, "Products")

    def test_catalog_section_hidden_for_owner_without_shop(self):
        # Shopless owners are redirected from dashboard to setup,
        # so use change-password (renders base.html without a shop).
        self.client.force_login(self.owner)
        response = self.client.get(reverse("accounts:change_password"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Catalog")
        self.assertNotContains(response, "Products")


class CatalogPublicHelperTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "catalog@example.com",
            "testpassword123",
            full_name="Catalog Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )

        self.shop = Shop.objects.create(
            owner=self.user,
            name="Test Shop",
            slug="test-shop",
            exchange_rate_lbp_per_usd="89500.00",
        )

        self.today = date.today()

    def test_shop_with_active_subscription_is_public(self):
        Subscription.objects.create(
            shop=self.shop,
            plan=Subscription.Plan.BASIC,
            status=Subscription.Status.ACTIVE,
            starts_on=self.today,
        )

        self.assertTrue(is_catalog_public(self.shop))

    def test_shop_with_no_subscription_is_not_public(self):
        self.assertFalse(is_catalog_public(self.shop))

    def test_expired_subscription_is_not_public(self):
        Subscription.objects.create(
            shop=self.shop,
            plan=Subscription.Plan.BASIC,
            status=Subscription.Status.EXPIRED,
            starts_on=self.today - timedelta(days=30),
            ends_on=self.today - timedelta(days=1),
        )

        self.assertFalse(is_catalog_public(self.shop))

    def test_cancelled_subscription_is_not_public(self):
        Subscription.objects.create(
            shop=self.shop,
            plan=Subscription.Plan.BASIC,
            status=Subscription.Status.CANCELLED,
            starts_on=self.today - timedelta(days=30),
        )

        self.assertFalse(is_catalog_public(self.shop))


class SubscriptionManagementTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "subscription-owner@example.com",
            "testpassword123",
            full_name="Subscription Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )

        self.admin = User.objects.create_user(
            "subscription-admin@example.com",
            "testpassword123",
            full_name="Subscription Admin",
            status=User.Status.ACTIVE,
            role=User.Role.ADMIN,
        )

        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Subscription Shop",
            slug="subscription-shop",
            exchange_rate_lbp_per_usd="89500.00",
        )

        self.subscription_list_url = reverse(
            "shops:subscription-list"
        )

    def test_admin_can_open_subscription_list(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            self.subscription_list_url
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "shops/subscription_list.html",
        )

    def test_shop_owner_cannot_access_subscription_list(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.subscription_list_url
        )

        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_is_redirected_to_login(self):
        response = self.client.get(
            self.subscription_list_url
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("accounts:login"),
            response.url,
        )

    def test_admin_can_create_subscription(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                "shops:subscription-create",
                args=[self.shop.pk],
            ),
            {
                "plan": Subscription.Plan.BASIC,
                "status": Subscription.Status.ACTIVE,
                "starts_on": self.today(),
                "ends_on": "",
            },
        )

        self.assertRedirects(
            response,
            self.subscription_list_url,
        )

        subscription = Subscription.objects.get(
            shop=self.shop
        )

        self.assertEqual(
            subscription.plan,
            Subscription.Plan.BASIC,
        )
        self.assertEqual(
            subscription.status,
            Subscription.Status.ACTIVE,
        )

    def test_admin_can_edit_subscription(self):
        subscription = Subscription.objects.create(
            shop=self.shop,
            plan=Subscription.Plan.FREE,
            status=Subscription.Status.EXPIRED,
            starts_on=date.today(),
        )

        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                "shops:subscription-edit",
                args=[subscription.pk],
            ),
            {
                "plan": Subscription.Plan.PREMIUM,
                "status": Subscription.Status.ACTIVE,
                "starts_on": date.today(),
                "ends_on": "",
            },
        )

        self.assertRedirects(
            response,
            self.subscription_list_url,
        )

        subscription.refresh_from_db()

        self.assertEqual(
            subscription.plan,
            Subscription.Plan.PREMIUM,
        )
        self.assertEqual(
            subscription.status,
            Subscription.Status.ACTIVE,
        )

    def test_shop_without_active_subscription_shows_waiting_banner(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("shops:dashboard")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Waiting for activation",
        )

    def test_shop_with_active_subscription_hides_waiting_banner(self):
        Subscription.objects.create(
            shop=self.shop,
            plan=Subscription.Plan.BASIC,
            status=Subscription.Status.ACTIVE,
            starts_on=date.today(),
        )

        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("shops:dashboard")
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            "Waiting for activation",
        )

    def test_subscription_form_rejects_end_date_before_start_date(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                "shops:subscription-create",
                args=[self.shop.pk],
            ),
            {
                "plan": Subscription.Plan.BASIC,
                "status": Subscription.Status.ACTIVE,
                "starts_on": "2026-09-20",
                "ends_on": "2026-09-19",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "End date cannot be before start date.",
        )

        self.assertFalse(
            Subscription.objects.filter(
                shop=self.shop
            ).exists()
        )

    def today(self):
        return date.today()


class SubscriptionIntegrityTests(TestCase):
    """SCRUM-61/63: one-ACTIVE-per-shop constraint, form guard, race safety,
    and subscription list showing non-ACTIVE subscriptions."""

    def setUp(self):
        self.owner = User.objects.create_user(
            "integrity-owner@example.com",
            "testpassword123",
            full_name="Integrity Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )

        self.admin = User.objects.create_user(
            "integrity-admin@example.com",
            "testpassword123",
            full_name="Integrity Admin",
            status=User.Status.ACTIVE,
            role=User.Role.ADMIN,
        )

        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Integrity Shop",
            slug="integrity-shop",
            exchange_rate_lbp_per_usd="89500.00",
        )

        self.today = date.today()
        self.list_url = reverse("shops:subscription-list")
        self.create_url = reverse(
            "shops:subscription-create", args=[self.shop.pk]
        )

    def _create_active(self, **overrides):
        defaults = {
            "shop": self.shop,
            "plan": Subscription.Plan.BASIC,
            "status": Subscription.Status.ACTIVE,
            "starts_on": self.today,
        }
        defaults.update(overrides)
        return Subscription.objects.create(**defaults)

    def _create_expired(self, **overrides):
        defaults = {
            "shop": self.shop,
            "plan": Subscription.Plan.BASIC,
            "status": Subscription.Status.EXPIRED,
            "starts_on": self.today - timedelta(days=30),
            "ends_on": self.today - timedelta(days=1),
        }
        defaults.update(overrides)
        return Subscription.objects.create(**defaults)

    # ------------------------------------------------------------------
    # Form guard: create blocked / allowed
    # ------------------------------------------------------------------

    def test_create_blocked_when_active_exists(self):
        self._create_active()
        self.client.force_login(self.admin)

        response = self.client.post(
            self.create_url,
            {
                "plan": Subscription.Plan.BASIC,
                "status": Subscription.Status.ACTIVE,
                "starts_on": self.today,
                "ends_on": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "This shop already has an active subscription.",
        )
        self.assertEqual(
            Subscription.objects.filter(shop=self.shop).count(), 1
        )

    def test_create_allowed_when_only_expired_exists(self):
        self._create_expired()
        self.client.force_login(self.admin)

        response = self.client.post(
            self.create_url,
            {
                "plan": Subscription.Plan.BASIC,
                "status": Subscription.Status.ACTIVE,
                "starts_on": self.today,
                "ends_on": "",
            },
        )

        self.assertRedirects(response, self.list_url)
        self.assertEqual(
            Subscription.objects.filter(
                shop=self.shop, status=Subscription.Status.ACTIVE
            ).count(),
            1,
        )

    def test_create_allowed_when_only_cancelled_exists(self):
        Subscription.objects.create(
            shop=self.shop,
            plan=Subscription.Plan.FREE,
            status=Subscription.Status.CANCELLED,
            starts_on=self.today - timedelta(days=30),
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            self.create_url,
            {
                "plan": Subscription.Plan.BASIC,
                "status": Subscription.Status.ACTIVE,
                "starts_on": self.today,
                "ends_on": "",
            },
        )

        self.assertRedirects(response, self.list_url)
        self.assertEqual(
            Subscription.objects.filter(
                shop=self.shop, status=Subscription.Status.ACTIVE
            ).count(),
            1,
        )

    def test_create_non_active_allowed_when_active_exists(self):
        """SCRUM-61: non-ACTIVE rows can be created even when ACTIVE exists."""
        self._create_active()
        self.client.force_login(self.admin)

        for status in (Subscription.Status.EXPIRED, Subscription.Status.CANCELLED):
            response = self.client.post(
                self.create_url,
                {
                    "plan": Subscription.Plan.FREE,
                    "status": status,
                    "starts_on": self.today - timedelta(days=60),
                    "ends_on": "",
                },
            )
            self.assertRedirects(response, self.list_url)
            self.assertTrue(
                Subscription.objects.filter(
                    shop=self.shop, status=status
                ).exists()
            )

    # ------------------------------------------------------------------
    # Form guard: edit blocked / allowed
    # ------------------------------------------------------------------

    def test_edit_expired_to_active_blocked_when_another_active_exists(self):
        self._create_active()
        expired = self._create_expired()
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("shops:subscription-edit", args=[expired.pk]),
            {
                "plan": Subscription.Plan.BASIC,
                "status": Subscription.Status.ACTIVE,
                "starts_on": self.today,
                "ends_on": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "This shop already has an active subscription.",
        )
        expired.refresh_from_db()
        self.assertEqual(expired.status, Subscription.Status.EXPIRED)

    def test_edit_expired_to_active_allowed_when_none_exists(self):
        expired = self._create_expired()
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("shops:subscription-edit", args=[expired.pk]),
            {
                "plan": Subscription.Plan.PREMIUM,
                "status": Subscription.Status.ACTIVE,
                "starts_on": self.today,
                "ends_on": "",
            },
        )

        self.assertRedirects(response, self.list_url)
        expired.refresh_from_db()
        self.assertEqual(expired.status, Subscription.Status.ACTIVE)
        self.assertEqual(expired.plan, Subscription.Plan.PREMIUM)

    def test_edit_active_row_itself_still_works(self):
        active = self._create_active(plan=Subscription.Plan.FREE)
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("shops:subscription-edit", args=[active.pk]),
            {
                "plan": Subscription.Plan.PREMIUM,
                "status": Subscription.Status.ACTIVE,
                "starts_on": self.today,
                "ends_on": "",
            },
        )

        self.assertRedirects(response, self.list_url)
        active.refresh_from_db()
        self.assertEqual(active.plan, Subscription.Plan.PREMIUM)
        self.assertEqual(active.status, Subscription.Status.ACTIVE)

    # ------------------------------------------------------------------
    # DB constraint (bypasses form)
    # ------------------------------------------------------------------

    def test_db_constraint_rejects_second_active_row(self):
        self._create_active()
        with self.assertRaises(IntegrityError):
            Subscription.objects.create(
                shop=self.shop,
                plan=Subscription.Plan.PREMIUM,
                status=Subscription.Status.ACTIVE,
                starts_on=self.today,
            )

    # ------------------------------------------------------------------
    # Race safety: view catches IntegrityError from save
    # ------------------------------------------------------------------

    def test_view_handles_integrity_error_on_create(self):
        self.client.force_login(self.admin)

        with patch("shops.views.Subscription.save") as mock_save:
            mock_save.side_effect = IntegrityError("duplicate active")
            response = self.client.post(
                self.create_url,
                {
                    "plan": Subscription.Plan.BASIC,
                    "status": Subscription.Status.ACTIVE,
                    "starts_on": self.today,
                    "ends_on": "",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "This shop already has an active subscription.",
        )
        self.assertEqual(
            Subscription.objects.filter(shop=self.shop).count(), 0
        )

    def test_view_handles_integrity_error_on_edit(self):
        active = self._create_active()
        self.client.force_login(self.admin)

        with patch("shops.views.Subscription.save") as mock_save:
            mock_save.side_effect = IntegrityError("duplicate active")
            response = self.client.post(
                reverse("shops:subscription-edit", args=[active.pk]),
                {
                    "plan": Subscription.Plan.PREMIUM,
                    "status": Subscription.Status.ACTIVE,
                    "starts_on": self.today,
                    "ends_on": "",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "This shop already has an active subscription.",
        )
        active.refresh_from_db()
        self.assertEqual(active.plan, Subscription.Plan.BASIC)

    # ------------------------------------------------------------------
    # SCRUM-63: subscription list
    # ------------------------------------------------------------------

    def test_list_shows_expired_row_with_edit_link_and_badge(self):
        expired = self._create_expired()
        self.client.force_login(self.admin)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Expired")
        self.assertContains(response, "status-badge-expired")
        self.assertContains(
            response,
            reverse("shops:subscription-edit", args=[expired.pk]),
        )

    def test_list_shows_create_when_no_active_exists(self):
        self._create_expired()
        self.client.force_login(self.admin)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("shops:subscription-create", args=[self.shop.pk]),
        )

    def test_list_shows_no_create_when_active_exists(self):
        self._create_active()
        self.client.force_login(self.admin)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            reverse("shops:subscription-create", args=[self.shop.pk]),
        )

    # ------------------------------------------------------------------
    # Access control
    # ------------------------------------------------------------------

    def test_non_admin_denied_on_create(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 403)

    def test_non_admin_denied_on_edit(self):
        active = self._create_active()
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("shops:subscription-edit", args=[active.pk])
        )
        self.assertEqual(response.status_code, 403)


class SubscriptionStatusHelperTests(TestCase):
    """Tests for get_latest_subscription() and subscription_status()."""

    def setUp(self):
        self.owner = User.objects.create_user(
            "status-owner@example.com",
            "testpassword123",
            full_name="Status Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Status Shop",
            slug="status-shop",
            exchange_rate_lbp_per_usd="89500.00",
        )
        self.today = date.today()

    def test_no_subscription_returns_none(self):
        self.assertIsNone(get_latest_subscription(self.shop))
        self.assertEqual(subscription_status(self.shop), "NONE")

    def test_active_subscription_returns_active(self):
        Subscription.objects.create(
            shop=self.shop,
            plan=Subscription.Plan.BASIC,
            status=Subscription.Status.ACTIVE,
            starts_on=self.today,
        )
        self.assertEqual(subscription_status(self.shop), "ACTIVE")

    def test_expired_subscription_returns_expired(self):
        Subscription.objects.create(
            shop=self.shop,
            plan=Subscription.Plan.BASIC,
            status=Subscription.Status.EXPIRED,
            starts_on=self.today - timedelta(days=30),
            ends_on=self.today - timedelta(days=1),
        )
        self.assertEqual(subscription_status(self.shop), "EXPIRED")

    def test_cancelled_subscription_returns_cancelled(self):
        Subscription.objects.create(
            shop=self.shop,
            plan=Subscription.Plan.BASIC,
            status=Subscription.Status.CANCELLED,
            starts_on=self.today - timedelta(days=30),
        )
        self.assertEqual(subscription_status(self.shop), "CANCELLED")

    def test_expired_then_active_picks_active(self):
        """Old EXPIRED row followed by newer ACTIVE row — most recent wins."""
        Subscription.objects.create(
            shop=self.shop,
            plan=Subscription.Plan.BASIC,
            status=Subscription.Status.EXPIRED,
            starts_on=self.today - timedelta(days=60),
            ends_on=self.today - timedelta(days=30),
        )
        Subscription.objects.create(
            shop=self.shop,
            plan=Subscription.Plan.BASIC,
            status=Subscription.Status.ACTIVE,
            starts_on=self.today,
        )
        self.assertEqual(subscription_status(self.shop), "ACTIVE")

    def test_active_then_expired_picks_expired(self):
        """Old ACTIVE row followed by newer EXPIRED row — most recent wins."""
        Subscription.objects.create(
            shop=self.shop,
            plan=Subscription.Plan.BASIC,
            status=Subscription.Status.ACTIVE,
            starts_on=self.today - timedelta(days=60),
        )
        Subscription.objects.create(
            shop=self.shop,
            plan=Subscription.Plan.BASIC,
            status=Subscription.Status.EXPIRED,
            starts_on=self.today,
            ends_on=self.today + timedelta(days=30),
        )
        self.assertEqual(subscription_status(self.shop), "EXPIRED")


class SubscriptionBannerTemplateTests(TestCase):
    """Template-level tests: banner text renders correctly per subscription state."""

    def setUp(self):
        self.owner = User.objects.create_user(
            "banner-owner@example.com",
            "testpassword123",
            full_name="Banner Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Banner Shop",
            slug="banner-shop",
            exchange_rate_lbp_per_usd="89500.00",
        )
        self.today = date.today()
        self.dashboard_url = reverse("shops:dashboard")

    def _assert_banner(self, response, expected_text, unexpected_texts=None):
        content = response.content.decode()
        self.assertIn("subscription-banner", content)
        self.assertIn(expected_text, content)
        if unexpected_texts:
            for text in unexpected_texts:
                self.assertNotIn(text, content)

    def test_no_subscription_shows_waiting_banner(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self._assert_banner(
            response,
            "Waiting for activation",
            unexpected_texts=["Subscription expired", "Subscription cancelled"],
        )

    def test_expired_subscription_shows_expired_banner(self):
        Subscription.objects.create(
            shop=self.shop,
            plan=Subscription.Plan.BASIC,
            status=Subscription.Status.EXPIRED,
            starts_on=self.today - timedelta(days=30),
            ends_on=self.today - timedelta(days=1),
        )
        self.client.force_login(self.owner)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self._assert_banner(
            response,
            "Subscription expired",
            unexpected_texts=["Waiting for activation", "Subscription cancelled"],
        )

    def test_cancelled_subscription_shows_cancelled_banner(self):
        Subscription.objects.create(
            shop=self.shop,
            plan=Subscription.Plan.BASIC,
            status=Subscription.Status.CANCELLED,
            starts_on=self.today - timedelta(days=30),
        )
        self.client.force_login(self.owner)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self._assert_banner(
            response,
            "Subscription cancelled",
            unexpected_texts=["Waiting for activation", "Subscription expired"],
        )

    def test_active_subscription_shows_no_banner(self):
        Subscription.objects.create(
            shop=self.shop,
            plan=Subscription.Plan.BASIC,
            status=Subscription.Status.ACTIVE,
            starts_on=self.today,
        )
        self.client.force_login(self.owner)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("subscription-banner", response.content.decode())

class DeliveryZoneTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "delivery-owner@example.com",
            "testpassword123",
            full_name="Delivery Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )

        self.other_owner = User.objects.create_user(
            "other-delivery-owner@example.com",
            "testpassword123",
            full_name="Other Delivery Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )

        self.admin = User.objects.create_user(
            "delivery-admin@example.com",
            "testpassword123",
            full_name="Delivery Admin",
            status=User.Status.ACTIVE,
            role=User.Role.ADMIN,
        )

        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Delivery Shop",
            slug="delivery-shop",
            exchange_rate_lbp_per_usd="89500.00",
        )

        self.other_shop = Shop.objects.create(
            owner=self.other_owner,
            name="Other Delivery Shop",
            slug="other-delivery-shop",
            exchange_rate_lbp_per_usd="89500.00",
        )

        self.zone = DeliveryZone.objects.create(
            shop=self.shop,
            area_name="Achrafieh",
            fee="5.00",
        )

        self.other_zone = DeliveryZone.objects.create(
            shop=self.other_shop,
            area_name="Hamra",
            fee="7.00",
        )

        self.client.force_login(self.owner)

    def test_unauthenticated_owner_list_is_redirected_to_login(self):
        self.client.logout()

        response = self.client.get(
            reverse(
                "shops:delivery-zone-list",
                kwargs={"shop_pk": self.shop.pk},
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("accounts:login"),
            response.url,
        )

    def test_owner_can_list_own_delivery_zones(self):
        response = self.client.get(
            reverse(
                "shops:delivery-zone-list",
                kwargs={"shop_pk": self.shop.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.zone.area_name)
        self.assertNotContains(response, self.other_zone.area_name)

    def test_owner_cannot_list_another_shops_delivery_zones(self):
        response = self.client.get(
            reverse(
                "shops:delivery-zone-list",
                kwargs={"shop_pk": self.other_shop.pk},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_admin_cannot_access_shop_owner_delivery_zones(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse(
                "shops:delivery-zone-list",
                kwargs={"shop_pk": self.shop.pk},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_owner_can_create_delivery_zone_for_own_shop(self):
        response = self.client.post(
            reverse(
                "shops:delivery-zone-create",
                kwargs={"shop_pk": self.shop.pk},
            ),
            {
                "area_name": "Jounieh",
                "fee": "6.50",
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 302)

        zone = DeliveryZone.objects.get(
            shop=self.shop,
            area_name="Jounieh",
        )

        self.assertEqual(zone.fee, 6.50)
        self.assertTrue(zone.is_active)

    def test_owner_cannot_create_delivery_zone_for_another_shop(self):
        response = self.client.post(
            reverse(
                "shops:delivery-zone-create",
                kwargs={"shop_pk": self.other_shop.pk},
            ),
            {
                "area_name": "Unauthorized Area",
                "fee": "4.00",
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            DeliveryZone.objects.filter(
                shop=self.other_shop,
                area_name="Unauthorized Area",
            ).exists()
        )

    def test_owner_can_create_inactive_delivery_zone(self):
        response = self.client.post(
            reverse(
                "shops:delivery-zone-create",
                kwargs={"shop_pk": self.shop.pk},
            ),
            {
                "area_name": "Inactive Area",
                "fee": "3.00",
                "is_active": False,
            },
        )

        self.assertEqual(response.status_code, 302)

        zone = DeliveryZone.objects.get(
            shop=self.shop,
            area_name="Inactive Area",
        )

        self.assertFalse(zone.is_active)

    def test_duplicate_area_name_is_rejected_within_same_shop(self):
        response = self.client.post(
            reverse(
                "shops:delivery-zone-create",
                kwargs={"shop_pk": self.shop.pk},
            ),
            {
                "area_name": "Achrafieh",
                "fee": "8.00",
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            DeliveryZone.objects.filter(
                shop=self.shop,
                area_name="Achrafieh",
            ).count(),
            1,
        )

    def test_same_area_name_is_allowed_in_different_shop(self):
        other_zone = DeliveryZone.objects.create(
            shop=self.other_shop,
            area_name="Achrafieh",
            fee="8.00",
        )

        self.assertEqual(
            other_zone.area_name,
            "Achrafieh",
        )
        self.assertEqual(
            DeliveryZone.objects.filter(
                area_name="Achrafieh",
            ).count(),
            2,
        )

    def test_negative_delivery_fee_is_rejected(self):
        response = self.client.post(
            reverse(
                "shops:delivery-zone-create",
                kwargs={"shop_pk": self.shop.pk},
            ),
            {
                "area_name": "Negative Fee Area",
                "fee": "-1.00",
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            DeliveryZone.objects.filter(
                shop=self.shop,
                area_name="Negative Fee Area",
            ).exists()
        )

    def test_owner_can_edit_own_delivery_zone(self):
        response = self.client.post(
            reverse(
                "shops:delivery-zone-edit",
                kwargs={
                    "shop_pk": self.shop.pk,
                    "zone_pk": self.zone.pk,
                },
            ),
            {
                "area_name": "Updated Area",
                "fee": "9.50",
                "is_active": False,
            },
        )

        self.assertEqual(response.status_code, 302)

        self.zone.refresh_from_db()

        self.assertEqual(
            self.zone.area_name,
            "Updated Area",
        )
        self.assertEqual(
            self.zone.fee,
            9.50,
        )
        self.assertFalse(self.zone.is_active)

    def test_owner_cannot_edit_another_shops_delivery_zone(self):
        response = self.client.post(
            reverse(
                "shops:delivery-zone-edit",
                kwargs={
                    "shop_pk": self.shop.pk,
                    "zone_pk": self.other_zone.pk,
                },
            ),
            {
                "area_name": "Should Not Change",
                "fee": "99.00",
                "is_active": False,
            },
        )

        self.assertEqual(response.status_code, 404)

        self.other_zone.refresh_from_db()

        self.assertEqual(
            self.other_zone.area_name,
            "Hamra",
        )
        self.assertEqual(
            self.other_zone.fee,
            7.00,
        )
        self.assertTrue(self.other_zone.is_active)

    def test_owner_can_delete_own_delivery_zone(self):
        response = self.client.post(
            reverse(
                "shops:delivery-zone-delete",
                kwargs={
                    "shop_pk": self.shop.pk,
                    "zone_pk": self.zone.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            DeliveryZone.objects.filter(
                pk=self.zone.pk,
            ).exists()
        )

    def test_owner_cannot_delete_another_shops_delivery_zone(self):
        response = self.client.post(
            reverse(
                "shops:delivery-zone-delete",
                kwargs={
                    "shop_pk": self.shop.pk,
                    "zone_pk": self.other_zone.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            DeliveryZone.objects.filter(
                pk=self.other_zone.pk,
            ).exists()
        )

    def test_delivery_zone_delete_rejects_get_request(self):
        response = self.client.get(
            reverse(
                "shops:delivery-zone-delete",
                kwargs={
                    "shop_pk": self.shop.pk,
                    "zone_pk": self.zone.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 405)

    def test_area_name_is_trimmed(self):
        response = self.client.post(
            reverse(
                "shops:delivery-zone-create",
                kwargs={"shop_pk": self.shop.pk},
            ),
            {
                "area_name": "  Downtown  ",
                "fee": "4.00",
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 302)

        zone = DeliveryZone.objects.get(
            shop=self.shop,
            area_name="Downtown",
        )

        self.assertEqual(zone.area_name, "Downtown")
