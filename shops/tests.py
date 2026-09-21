
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from accounts.models import User
from .models import Shop


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
