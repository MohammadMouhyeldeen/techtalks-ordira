from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .models import Shop


class SidebarLinkTests(TestCase):
    """SCRUM-98: Customers/Delivery Zones links in the sidebar plus the
    Account > Settings link. Mirrors SidebarCatalogSectionTests fixtures."""

    def setUp(self):
        self.owner = User.objects.create_user(
            "sidebar-links-owner@example.com",
            "testpassword123",
            full_name="Sidebar Links Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )

    def _create_shop_for(self, owner):
        return Shop.objects.create(
            owner=owner,
            name="Sidebar Links Shop",
            slug="sidebar-links-shop",
            exchange_rate_lbp_per_usd="89500.00",
        )

    def test_links_render_for_owner_with_shop(self):
        shop = self._create_shop_for(self.owner)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("shops:dashboard"))
        self.assertEqual(response.status_code, 200)
        customers_url = reverse("customers:list", args=[shop.pk])
        delivery_zones_url = reverse("shops:delivery-zone-list", args=[shop.pk])
        settings_url = reverse("shops:settings")
        self.assertContains(response, 'href="{}"'.format(customers_url))
        self.assertContains(response, 'href="{}"'.format(delivery_zones_url))
        self.assertContains(response, 'href="{}"'.format(settings_url))

    def test_links_hidden_for_owner_without_shop(self):
        # Shopless owners are redirected from dashboard to setup, so use
        # change-password (renders base.html with the sidebar, no shop).
        self.client.force_login(self.owner)
        response = self.client.get(reverse("accounts:change_password"))
        self.assertEqual(response.status_code, 200)
        # The sidebar really rendered: Shop Settings sits outside the guard.
        self.assertContains(response, 'href="{}"'.format(reverse("shops:settings")))
        # Guarded links need shop.pk, so they must be absent for shopless
        # users; a non-guarded {% url %} here would raise NoReverseMatch/500.
        # Dummy pk=1: no shops exist in this test's database.
        self.assertNotContains(
            response, 'href="{}"'.format(reverse("customers:list", args=[1]))
        )
        self.assertNotContains(
            response,
            'href="{}"'.format(reverse("shops:delivery-zone-list", args=[1])),
        )

    def test_account_settings_link_is_not_dead(self):
        # change-password avoids dashboard.html, whose own shops:settings
        # link would inflate the count: exactly 2 remain (Shop section,
        # previously L34, and Account section, previously L158).
        self.client.force_login(self.owner)
        response = self.client.get(reverse("accounts:change_password"))
        self.assertEqual(response.status_code, 200)
        settings_url = reverse("shops:settings")
        self.assertEqual(
            response.content.count('href="{}"'.format(settings_url).encode()), 2
        )
