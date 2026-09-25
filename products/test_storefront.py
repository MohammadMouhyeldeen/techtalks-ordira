from datetime import date

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from shops.models import Shop, Subscription

from .models import Category, Product, ProductVariant


class PublicCatalogViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "storefront-owner@example.com",
            "testpassword123",
            full_name="Storefront Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Sara's Closet",
            slug="saras-closet",
            exchange_rate_lbp_per_usd="89500.00",
        )
        Subscription.objects.create(
            shop=self.shop,
            plan=Subscription.Plan.BASIC,
            status=Subscription.Status.ACTIVE,
            starts_on=date.today(),
        )

        self.category = Category.objects.create(shop=self.shop, name="Clothing")
        self.product = Product.objects.create(
            shop=self.shop,
            category=self.category,
            name="Linen Shirt",
            description="Breathable linen shirt.",
        )
        ProductVariant.objects.create(
            product=self.product,
            color="Sand",
            size="M",
            unit_price="28.00",
            stock_quantity=5,
        )

        self.catalog_url = reverse("public_catalog", args=[self.shop.slug])

    def test_renders_real_products_for_active_shop(self):
        response = self.client.get(self.catalog_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Linen Shirt")

    def test_products_from_other_shops_do_not_leak_in(self):
        other_owner = User.objects.create_user(
            "other-owner@example.com",
            "testpassword123",
            full_name="Other Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        other_shop = Shop.objects.create(
            owner=other_owner,
            name="Other Shop",
            slug="other-shop",
            exchange_rate_lbp_per_usd="89500.00",
        )
        other_category = Category.objects.create(shop=other_shop, name="Accessories")
        other_product = Product.objects.create(
            shop=other_shop,
            category=other_category,
            name="Tote Bag",
        )
        ProductVariant.objects.create(
            product=other_product, color="Natural", size="One size",
            unit_price="18.00", stock_quantity=10,
        )

        response = self.client.get(self.catalog_url)

        self.assertNotContains(response, "Tote Bag")

    def test_inactive_product_is_not_shown(self):
        inactive = Product.objects.create(
            shop=self.shop,
            category=self.category,
            name="Retired Hoodie",
            is_active=False,
        )
        ProductVariant.objects.create(
            product=inactive, color="Gray", size="M",
            unit_price="30.00", stock_quantity=5,
        )

        response = self.client.get(self.catalog_url)

        self.assertNotContains(response, "Retired Hoodie")

    def test_product_with_no_variants_is_not_shown(self):
        Product.objects.create(
            shop=self.shop,
            category=self.category,
            name="Unpriced Ghost Product",
        )

        response = self.client.get(self.catalog_url)

        self.assertNotContains(response, "Unpriced Ghost Product")

    def test_category_chip_reflects_real_shop_category(self):
        response = self.client.get(self.catalog_url)

        self.assertContains(response, 'data-filter="clothing"')
        self.assertContains(response, "Clothing")

    def test_category_with_no_active_products_has_no_chip(self):
        Category.objects.create(shop=self.shop, name="Empty Category")

        response = self.client.get(self.catalog_url)

        self.assertNotContains(response, "Empty Category")

    def test_unknown_slug_returns_not_found(self):
        response = self.client.get(reverse("public_catalog", args=["does-not-exist"]))

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "storefront/unavailable.html")

    def test_shop_without_subscription_shows_unavailable_state(self):
        self.shop.subscriptions.all().delete()

        response = self.client.get(self.catalog_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "storefront/unavailable.html")
        self.assertNotContains(response, "Linen Shirt")

    def test_shop_with_expired_subscription_shows_unavailable_state(self):
        self.shop.subscriptions.all().delete()
        Subscription.objects.create(
            shop=self.shop,
            plan=Subscription.Plan.BASIC,
            status=Subscription.Status.EXPIRED,
            starts_on=date.today(),
        )

        response = self.client.get(self.catalog_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "storefront/unavailable.html")

    def test_empty_shop_shows_empty_state_copy(self):
        self.product.delete()

        response = self.client.get(self.catalog_url)

        self.assertContains(response, "hasn't added any products yet")


class ProductDetailViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "detail-owner@example.com",
            "testpassword123",
            full_name="Detail Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Sara's Closet",
            slug="saras-closet-detail",
            exchange_rate_lbp_per_usd="89500.00",
        )
        Subscription.objects.create(
            shop=self.shop,
            plan=Subscription.Plan.BASIC,
            status=Subscription.Status.ACTIVE,
            starts_on=date.today(),
        )
        self.category = Category.objects.create(shop=self.shop, name="Clothing")
        self.product = Product.objects.create(
            shop=self.shop,
            category=self.category,
            name="Denim Jacket",
            description="Classic denim jacket.",
        )
        self.in_stock_variant = ProductVariant.objects.create(
            product=self.product, color="Indigo", size="M",
            unit_price="45.00", stock_quantity=6,
        )
        self.out_of_stock_variant = ProductVariant.objects.create(
            product=self.product, color="Indigo", size="L",
            unit_price="45.00", stock_quantity=0,
        )

        self.detail_url = reverse(
            "product_detail", args=[self.shop.slug, self.product.pk]
        )

    def test_renders_real_product_detail(self):
        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Denim Jacket")
        self.assertContains(response, 'data-stock="6"')

    def test_out_of_stock_variant_pill_is_disabled(self):
        response = self.client.get(self.detail_url)
        content = response.content.decode()

        # "disabled" is rendered after data-stock, before the tag's closing '>'.
        start = content.index('data-stock="0"')
        tag_tail = content[start:content.index(">", start)]
        self.assertIn("disabled", tag_tail)

    def test_in_stock_variant_pill_is_not_disabled(self):
        response = self.client.get(self.detail_url)
        content = response.content.decode()

        start = content.index('data-stock="6"')
        tag_tail = content[start:content.index(">", start)]
        self.assertNotIn("disabled", tag_tail)

    def test_404_for_product_in_different_shop(self):
        other_owner = User.objects.create_user(
            "other-detail-owner@example.com",
            "testpassword123",
            full_name="Other Detail Owner",
            status=User.Status.ACTIVE,
            role=User.Role.SHOP_OWNER,
        )
        other_shop = Shop.objects.create(
            owner=other_owner,
            name="Other Shop",
            slug="other-detail-shop",
            exchange_rate_lbp_per_usd="89500.00",
        )
        Subscription.objects.create(
            shop=other_shop,
            plan=Subscription.Plan.BASIC,
            status=Subscription.Status.ACTIVE,
            starts_on=date.today(),
        )

        response = self.client.get(
            reverse("product_detail", args=[other_shop.slug, self.product.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "storefront/unavailable.html")

    def test_404_for_inactive_product(self):
        self.product.is_active = False
        self.product.save()

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 404)

    def test_related_products_scoped_to_shop_and_category(self):
        same_category_product = Product.objects.create(
            shop=self.shop, category=self.category, name="Wool Sweater",
        )
        ProductVariant.objects.create(
            product=same_category_product, color="Charcoal", size="M",
            unit_price="38.00", stock_quantity=3,
        )

        other_category = Category.objects.create(shop=self.shop, name="Accessories")
        other_category_product = Product.objects.create(
            shop=self.shop, category=other_category, name="Leather Belt",
        )
        ProductVariant.objects.create(
            product=other_category_product, color="Brown", size="M",
            unit_price="24.00", stock_quantity=10,
        )

        response = self.client.get(self.detail_url)

        self.assertContains(response, "Wool Sweater")
        self.assertNotContains(response, "Leather Belt")

    def test_no_hex_swatch_leaks_into_response(self):
        response = self.client.get(self.detail_url)

        self.assertNotContains(response, "background:#")

    def test_shop_without_subscription_shows_unavailable_before_product_lookup(self):
        self.shop.subscriptions.all().delete()

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "storefront/unavailable.html")
