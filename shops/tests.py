from django.test import TestCase
from django.urls import reverse

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
        self.assertTemplateUsed(response, "shops/shop_setup.html")

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
        self.assertEqual(shop.whatsapp, "+96170123456")
        self.assertEqual(shop.instagram, "@testfashion")
        self.assertTrue(shop.pickup_available)
        self.assertEqual(
            str(shop.exchange_rate_lbp_per_usd),
            "89500.00",
        )

    def test_duplicate_slug_is_rejected(self):
        self.client.force_login(self.user)

        Shop.objects.create(
            owner=self.user,
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
            "already exists",
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
            Shop.objects.filter(slug="invalid-rate-shop").exists()
        )
