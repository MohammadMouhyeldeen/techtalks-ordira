
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import resolve, reverse
from django.test import RequestFactory

from accounts.models import User
from shops.models import Shop


class SidebarRenderingTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin = User.objects.create_user(
            email="admin-sidebar@example.com",
            password="TestPassword123!",
            full_name="Sidebar Admin",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
        )
        self.owner = User.objects.create_user(
            email="owner-sidebar@example.com",
            password="TestPassword123!",
            full_name="Sidebar Owner",
            role=User.Role.SHOP_OWNER,
            status=User.Status.ACTIVE,
        )
        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Sidebar Shop",
            slug="sidebar-shop",
            exchange_rate_lbp_per_usd=89500,
        )

    def test_customers_link_is_highlighted_when_active(self):
        html = self.render_sidebar(
            self.owner,
            self.shop,
            view_name="customers:list",
        )

        self.assertIn(
            'class="sidebar-link active"',
            html,
        )

    def test_delivery_zones_link_is_highlighted_when_active(self):
        html = self.render_sidebar(
            self.owner,
            self.shop,
            view_name="shops:delivery-zone-list",
        )

        self.assertIn(
            'class="sidebar-link active"',
            html,
        )

    def test_settings_link_is_highlighted_when_active(self):
        html = self.render_sidebar(
            self.owner,
            self.shop,
            view_name="shops:settings",
        )

        self.assertIn(
            'class="sidebar-link active"',
            html,
        )


    def render_sidebar(self, user, shop=None, view_name="shops:dashboard"):
        request = self.factory.get("/")
        request.user = user
        request.resolver_match = SimpleNamespace(view_name=view_name)

        return render_to_string(
            "components/sidebar.html",
            {"request": request, "shop": shop},
        )

    def test_admin_renders_sidebar_without_shop_links(self):
        html = self.render_sidebar(self.admin)

        self.assertIn(reverse("shops:dashboard"), html)
        self.assertNotIn(reverse("shops:delivery-zone-list", kwargs={
            "shop_pk": self.shop.pk,
        }), html)
        self.assertNotIn('href="#"', html)
        self.assertNotIn("Inventory", html)

    def test_owner_with_shop_sees_correct_shop_links(self):
        html = self.render_sidebar(self.owner, self.shop)

        self.assertIn(reverse("customers:list", kwargs={"shop_pk": shop.pk}), html)
        self.assertIn(
            reverse(
                "shops:delivery-zone-list",
                kwargs={"shop_pk": self.shop.pk},
            ),
            html,
        )
        self.assertIn(reverse("shops:settings"), html)
        self.assertIn(
            reverse(
                "products:product-list",
                kwargs={"shop_pk": self.shop.pk},
            ),
            html,
        )
        self.assertNotIn('href="#"', html)
        self.assertNotIn("Inventory", html)

    def test_owner_without_shop_renders_without_shop_specific_links(self):
        html = self.render_sidebar(self.owner, shop=None)

        self.assertIn(reverse("shops:dashboard"), html)
        self.assertNotIn("Delivery Zones", html)
        self.assertNotIn("Customers", html)
        self.assertNotIn("Products", html)
        self.assertNotIn("Inventory", html)
        self.assertNotIn('href="#"', html)
