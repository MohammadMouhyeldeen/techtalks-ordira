from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from shops.models import Shop

from .forms import (
    CategoryForm,
    ProductForm,
    ProductVariantForm,
    StockAdjustmentForm,
)
from .models import Category, Product, ProductVariant, StockMovement
from .services import adjust_variant_stock


class ProductFormTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="testpass123",
            full_name="First Owner",
            status=User.Status.ACTIVE,
        )
        self.other_owner = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            full_name="Second Owner",
            status=User.Status.ACTIVE,
        )

        self.shop = Shop.objects.create(
            owner=self.owner,
            name="First Shop",
            slug="first-shop",
            exchange_rate_lbp_per_usd=Decimal("90000.00"),
        )
        self.other_shop = Shop.objects.create(
            owner=self.other_owner,
            name="Other Shop",
            slug="other-shop",
            exchange_rate_lbp_per_usd=Decimal("90000.00"),
        )

        self.category = Category.objects.create(
            shop=self.shop,
            name="Clothing",
        )
        self.other_category = Category.objects.create(
            shop=self.other_shop,
            name="Accessories",
        )

        self.product = Product.objects.create(
            shop=self.shop,
            category=self.category,
            name="T-Shirt",
        )

    def test_category_form_rejects_duplicate_name_in_same_shop(self):
        form = CategoryForm(
            data={"name": "clothing"},
            shop=self.shop,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)
        self.assertIn("already exists", form.errors["name"][0])

    def test_same_category_name_is_allowed_in_another_shop(self):
        form = CategoryForm(
            data={"name": "Clothing"},
            shop=self.other_shop,
        )

        self.assertTrue(form.is_valid())

    def test_product_form_only_shows_categories_from_owner_shop(self):
        form = ProductForm(shop=self.shop)
        categories = form.fields["category"].queryset

        self.assertIn(self.category, categories)
        self.assertNotIn(self.other_category, categories)

    def test_product_form_rejects_category_from_another_shop(self):
        form = ProductForm(
            data={
                "name": "Invalid Product",
                "description": "",
                "category": self.other_category.pk,
                "is_active": True,
            },
            shop=self.shop,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("category", form.errors)

    def test_archived_current_category_remains_available_when_editing(self):
        archived_category = Category.objects.create(
            shop=self.shop,
            name="Archived",
            is_active=False,
        )
        product = Product.objects.create(
            shop=self.shop,
            category=archived_category,
            name="Old Product",
        )

        form = ProductForm(
            instance=product,
            shop=self.shop,
        )

        self.assertIn(
            archived_category,
            form.fields["category"].queryset,
        )

    def test_product_model_rejects_category_from_another_shop(self):
        product = Product(
            shop=self.shop,
            category=self.other_category,
            name="Invalid Product",
        )

        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_variant_form_rejects_duplicate_color_and_size(self):
        ProductVariant.objects.create(
            product=self.product,
            color="Black",
            size="M",
            unit_price=Decimal("20.00"),
            currency=ProductVariant.Currency.USD,
            stock_quantity=5,
            low_stock_threshold=1,
        )

        form = ProductVariantForm(
            data={
                "color": "black",
                "size": "m",
                "unit_price": "22.00",
                "currency": ProductVariant.Currency.USD,
                "stock_quantity": 3,
                "low_stock_threshold": 1,
            },
            product=self.product,
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            "already exists",
            str(form.non_field_errors()),
        )
    def test_variant_form_does_not_allow_direct_stock_editing(self):
        form = ProductVariantForm(product=self.product)

        self.assertNotIn("stock_quantity", form.fields)

class CategoryViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="view-owner@example.com",
            password="testpass123",
            full_name="View Owner",
            status=User.Status.ACTIVE,
        )
        self.other_owner = User.objects.create_user(
            email="other-view-owner@example.com",
            password="testpass123",
            full_name="Other View Owner",
            status=User.Status.ACTIVE,
        )

        self.shop = Shop.objects.create(
            owner=self.owner,
            name="View Shop",
            slug="view-shop",
            exchange_rate_lbp_per_usd=Decimal("90000.00"),
        )
        self.other_shop = Shop.objects.create(
            owner=self.other_owner,
            name="Other View Shop",
            slug="other-view-shop",
            exchange_rate_lbp_per_usd=Decimal("90000.00"),
        )

        self.category = Category.objects.create(
            shop=self.shop,
            name="Clothing",
        )
        self.other_category = Category.objects.create(
            shop=self.other_shop,
            name="Accessories",
        )

        self.client.force_login(self.owner)

    def test_owner_can_create_category_for_own_shop(self):
        url = reverse(
            "products:category-create",
            kwargs={"shop_pk": self.shop.pk},
        )

        response = self.client.post(
            url,
            {"name": "Shoes"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Category.objects.filter(
                shop=self.shop,
                name="Shoes",
            ).exists()
        )

    def test_owner_cannot_create_category_for_another_shop(self):
        url = reverse(
            "products:category-create",
            kwargs={"shop_pk": self.other_shop.pk},
        )

        response = self.client.post(
            url,
            {"name": "Forbidden Category"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            Category.objects.filter(
                shop=self.other_shop,
                name="Forbidden Category",
            ).exists()
        )

    def test_owner_can_archive_own_category(self):
        url = reverse(
            "products:category-archive",
            kwargs={
                "shop_pk": self.shop.pk,
                "category_pk": self.category.pk,
            },
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)

        self.category.refresh_from_db()
        self.assertFalse(self.category.is_active)

    def test_owner_cannot_archive_another_shops_category(self):
        url = reverse(
            "products:category-archive",
            kwargs={
                "shop_pk": self.shop.pk,
                "category_pk": self.other_category.pk,
            },
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, 404)

        self.other_category.refresh_from_db()
        self.assertTrue(self.other_category.is_active)

    def test_category_archive_rejects_get_request(self):
        url = reverse(
            "products:category-archive",
            kwargs={
                "shop_pk": self.shop.pk,
                "category_pk": self.category.pk,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 405)



class ProductViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="product-owner@example.com",
            password="testpass123",
            full_name="Product Owner",
            status=User.Status.ACTIVE,
        )
        self.other_owner = User.objects.create_user(
            email="other-product-owner@example.com",
            password="testpass123",
            full_name="Other Product Owner",
            status=User.Status.ACTIVE,
        )

        self.shop = Shop.objects.create(
            owner=self.owner,
            name="First Shop",
            slug="first-product-shop",
            exchange_rate_lbp_per_usd="90000.00",
        )
        self.other_shop = Shop.objects.create(
            owner=self.other_owner,
            name="Other Shop",
            slug="other-product-shop",
            exchange_rate_lbp_per_usd="90000.00",
        )

        self.category = Category.objects.create(
            shop=self.shop,
            name="Clothing",
        )
        self.other_category = Category.objects.create(
            shop=self.other_shop,
            name="Accessories",
        )

        self.product = Product.objects.create(
            shop=self.shop,
            category=self.category,
            name="T-shirt",
            description="Classic cotton T-shirt",
        )
        self.other_product = Product.objects.create(
            shop=self.other_shop,
            category=self.other_category,
            name="Handbag",
        )

        self.client.force_login(self.owner)

    def test_owner_can_create_product_for_own_shop(self):
        url = reverse(
            "products:product-create",
            kwargs={"shop_pk": self.shop.pk},
        )

        response = self.client.post(
            url,
            {
                "name": "Summer Dress",
                "description": "Light summer dress",
                "category": self.category.pk,
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Product.objects.filter(
                shop=self.shop,
                name="Summer Dress",
            ).exists()
        )

    def test_owner_cannot_create_product_for_another_shop(self):
        url = reverse(
            "products:product-create",
            kwargs={"shop_pk": self.other_shop.pk},
        )

        response = self.client.post(
            url,
            {
                "name": "Unauthorized Product",
                "description": "",
                "category": self.other_category.pk,
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            Product.objects.filter(name="Unauthorized Product").exists()
        )

    def test_owner_can_edit_own_product(self):
        url = reverse(
            "products:product-edit",
            kwargs={
                "shop_pk": self.shop.pk,
                "product_pk": self.product.pk,
            },
        )

        response = self.client.post(
            url,
            {
                "name": "Updated T-shirt",
                "description": "Updated description",
                "category": self.category.pk,
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 302)

        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Updated T-shirt")
        self.assertEqual(
            self.product.description,
            "Updated description",
        )

    def test_owner_cannot_edit_another_shops_product(self):
        url = reverse(
            "products:product-edit",
            kwargs={
                "shop_pk": self.other_shop.pk,
                "product_pk": self.other_product.pk,
            },
        )

        response = self.client.post(
            url,
            {
                "name": "Changed Handbag",
                "description": "",
                "category": self.other_category.pk,
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 404)

        self.other_product.refresh_from_db()
        self.assertEqual(self.other_product.name, "Handbag")

    def test_owner_cannot_view_another_shops_product(self):
        url = reverse(
            "products:product-detail",
            kwargs={
                "shop_pk": self.other_shop.pk,
                "product_pk": self.other_product.pk,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_owner_can_archive_own_product(self):
        url = reverse(
            "products:product-archive",
            kwargs={
                "shop_pk": self.shop.pk,
                "product_pk": self.product.pk,
            },
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)

        self.product.refresh_from_db()
        self.assertFalse(self.product.is_active)

    def test_owner_cannot_archive_another_shops_product(self):
        url = reverse(
            "products:product-archive",
            kwargs={
                "shop_pk": self.other_shop.pk,
                "product_pk": self.other_product.pk,
            },
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, 404)

        self.other_product.refresh_from_db()
        self.assertTrue(self.other_product.is_active)

    def test_product_archive_rejects_get_request(self):
        url = reverse(
            "products:product-archive",
            kwargs={
                "shop_pk": self.shop.pk,
                "product_pk": self.product.pk,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 405)

class ProductVariantModelTests(TestCase):
    def test_stock_below_threshold_is_low_stock(self):
        variant = ProductVariant(
            stock_quantity=2,
            low_stock_threshold=3,
        )

        self.assertTrue(variant.is_low_stock)

    def test_stock_equal_to_threshold_is_low_stock(self):
        variant = ProductVariant(
            stock_quantity=3,
            low_stock_threshold=3,
        )

        self.assertTrue(variant.is_low_stock)

    def test_stock_above_threshold_is_not_low_stock(self):
        variant = ProductVariant(
            stock_quantity=4,
            low_stock_threshold=3,
        )

        self.assertFalse(variant.is_low_stock)

class ProductVariantViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="variant-owner@example.com",
            password="testpass123",
            full_name="Variant Owner",
            status=User.Status.ACTIVE,
        )
        self.other_owner = User.objects.create_user(
            email="other-variant-owner@example.com",
            password="testpass123",
            full_name="Other Variant Owner",
            status=User.Status.ACTIVE,
        )

        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Variant Shop",
            slug="variant-shop",
            exchange_rate_lbp_per_usd="90000.00",
        )
        self.other_shop = Shop.objects.create(
            owner=self.other_owner,
            name="Other Variant Shop",
            slug="other-variant-shop",
            exchange_rate_lbp_per_usd="90000.00",
        )

        self.category = Category.objects.create(
            shop=self.shop,
            name="Clothing",
        )
        self.other_category = Category.objects.create(
            shop=self.other_shop,
            name="Accessories",
        )

        self.product = Product.objects.create(
            shop=self.shop,
            category=self.category,
            name="T-shirt",
        )
        self.other_product = Product.objects.create(
            shop=self.other_shop,
            category=self.other_category,
            name="Handbag",
        )

        self.variant = ProductVariant.objects.create(
            product=self.product,
            color="Black",
            size="M",
            unit_price="20.00",
            currency=ProductVariant.Currency.USD,
            stock_quantity=10,
            low_stock_threshold=2,
        )
        self.other_variant = ProductVariant.objects.create(
            product=self.other_product,
            color="Brown",
            size="One Size",
            unit_price="30.00",
            currency=ProductVariant.Currency.USD,
            stock_quantity=5,
            low_stock_threshold=1,
        )

        self.client.force_login(self.owner)

    def test_owner_can_create_variant_for_own_product(self):
        url = reverse(
            "products:variant-create",
            kwargs={
                "shop_pk": self.shop.pk,
                "product_pk": self.product.pk,
            },
        )

        response = self.client.post(
            url,
            {
                "color": "White",
                "size": "L",
                "unit_price": "22.00",
                "currency": ProductVariant.Currency.USD,
                "stock_quantity": 7,
                "low_stock_threshold": 2,
            },
        )

        self.assertEqual(response.status_code, 302)

        variant = ProductVariant.objects.get(
            product=self.product,
            color="White",
            size="L",
        )

        self.assertEqual(variant.stock_quantity, 0)
        self.assertFalse(
            StockMovement.objects.filter(variant=variant).exists()
        )

    def test_owner_cannot_create_variant_for_another_product(self):
        url = reverse(
            "products:variant-create",
            kwargs={
                "shop_pk": self.other_shop.pk,
                "product_pk": self.other_product.pk,
            },
        )

        response = self.client.post(
            url,
            {
                "color": "Red",
                "size": "S",
                "unit_price": "25.00",
                "currency": ProductVariant.Currency.USD,
                "stock_quantity": 4,
                "low_stock_threshold": 1,
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            ProductVariant.objects.filter(
                product=self.other_product,
                color="Red",
                size="S",
            ).exists()
        )

    def test_owner_can_edit_own_variant(self):
        url = reverse(
            "products:variant-edit",
            kwargs={
                "shop_pk": self.shop.pk,
                "product_pk": self.product.pk,
                "variant_pk": self.variant.pk,
            },
        )

        response = self.client.post(
            url,
            {
                "color": "Navy",
                "size": "M",
                "unit_price": "24.00",
                "currency": ProductVariant.Currency.USD,
                "stock_quantity": 12,
                "low_stock_threshold": 3,
            },
        )

        self.assertEqual(response.status_code, 302)

        self.variant.refresh_from_db()
        self.assertEqual(self.variant.color, "Navy")
        self.assertEqual(self.variant.stock_quantity, 10)
        self.assertEqual(self.variant.low_stock_threshold, 3)

    def test_owner_cannot_edit_another_shops_variant(self):
        url = reverse(
            "products:variant-edit",
            kwargs={
                "shop_pk": self.other_shop.pk,
                "product_pk": self.other_product.pk,
                "variant_pk": self.other_variant.pk,
            },
        )

        response = self.client.post(
            url,
            {
                "color": "Changed",
                "size": "One Size",
                "unit_price": "35.00",
                "currency": ProductVariant.Currency.USD,
                "stock_quantity": 6,
                "low_stock_threshold": 1,
            },
        )

        self.assertEqual(response.status_code, 404)

        self.other_variant.refresh_from_db()
        self.assertEqual(self.other_variant.color, "Brown")

    def test_owner_cannot_view_another_shops_variant(self):
        url = reverse(
            "products:variant-detail",
            kwargs={
                "shop_pk": self.other_shop.pk,
                "product_pk": self.other_product.pk,
                "variant_pk": self.other_variant.pk,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_owner_can_delete_own_variant(self):
        url = reverse(
            "products:variant-delete",
            kwargs={
                "shop_pk": self.shop.pk,
                "product_pk": self.product.pk,
                "variant_pk": self.variant.pk,
            },
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            ProductVariant.objects.filter(pk=self.variant.pk).exists()
        )

    def test_owner_cannot_delete_another_shops_variant(self):
        url = reverse(
            "products:variant-delete",
            kwargs={
                "shop_pk": self.other_shop.pk,
                "product_pk": self.other_product.pk,
                "variant_pk": self.other_variant.pk,
            },
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            ProductVariant.objects.filter(
                pk=self.other_variant.pk
            ).exists()
        )

    def test_variant_delete_rejects_get_request(self):
        url = reverse(
            "products:variant-delete",
            kwargs={
                "shop_pk": self.shop.pk,
                "product_pk": self.product.pk,
                "variant_pk": self.variant.pk,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 405)

    def test_variant_with_stock_movement_is_archived_instead_of_deleted(self):
        StockMovement.objects.create(
            variant=self.variant,
            created_by=self.owner,
            change_qty=5,
            reason=StockMovement.Reason.RESTOCK,
        )

        url = reverse(
            "products:variant-delete",
            kwargs={
                "shop_pk": self.shop.pk,
                "product_pk": self.product.pk,
                "variant_pk": self.variant.pk,
            },
        )

        response = self.client.post(url)

        self.assertRedirects(
            response,
            reverse(
                "products:product-detail",
                kwargs={
                    "shop_pk": self.shop.pk,
                    "product_pk": self.product.pk,
                },
            ),
            fetch_redirect_response=False,
        )

        self.variant.refresh_from_db()

        self.assertFalse(self.variant.is_active)
        self.assertTrue(
            StockMovement.objects.filter(
                variant=self.variant,
            ).exists()
        )

    def test_archived_variant_cannot_be_viewed(self):
        self.variant.is_active = False
        self.variant.save(update_fields=["is_active"])

        url = reverse(
            "products:variant-detail",
            kwargs={
                "shop_pk": self.shop.pk,
                "product_pk": self.product.pk,
                "variant_pk": self.variant.pk,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)


    def test_archived_variant_cannot_be_edited(self):
        self.variant.is_active = False
        self.variant.save(update_fields=["is_active"])

        url = reverse(
            "products:variant-edit",
            kwargs={
                "shop_pk": self.shop.pk,
                "product_pk": self.product.pk,
                "variant_pk": self.variant.pk,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)


    def test_archived_variant_cannot_be_deleted_again(self):
        self.variant.is_active = False
        self.variant.save(update_fields=["is_active"])

        url = reverse(
            "products:variant-delete",
            kwargs={
                "shop_pk": self.shop.pk,
                "product_pk": self.product.pk,
                "variant_pk": self.variant.pk,
            },
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, 404)

        self.variant.refresh_from_db()
        self.assertFalse(self.variant.is_active)

    def test_owner_can_adjust_variant_stock(self):
        url = reverse(
            "products:variant-stock-adjust",
            kwargs={
                "shop_pk": self.shop.pk,
                "product_pk": self.product.pk,
                "variant_pk": self.variant.pk,
            },
        )

        response = self.client.post(
            url,
            {
                "change_qty": 5,
                "reason": StockMovement.Reason.RESTOCK,
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "products:product-detail",
                kwargs={
                    "shop_pk": self.shop.pk,
                    "product_pk": self.product.pk,
                },
            ),
            fetch_redirect_response=False,
        )

        self.variant.refresh_from_db()

        self.assertEqual(self.variant.stock_quantity, 15)

        movement = StockMovement.objects.get(
            variant=self.variant,
        )

        self.assertEqual(movement.change_qty, 5)
        self.assertEqual(
            movement.reason,
            StockMovement.Reason.RESTOCK,
        )
        self.assertEqual(movement.created_by, self.owner)

    def test_stock_adjustment_cannot_make_quantity_negative(self):
        url = reverse(
            "products:variant-stock-adjust",
            kwargs={
                "shop_pk": self.shop.pk,
                "product_pk": self.product.pk,
                "variant_pk": self.variant.pk,
            },
        )

        with patch(
            "products.views.render",
            return_value=HttpResponse(),
        ) as mocked_render:
            response = self.client.post(
                url,
                {
                    "change_qty": -11,
                    "reason": StockMovement.Reason.ADJUSTMENT,
                },
            )

        self.assertEqual(response.status_code, 200)

        self.variant.refresh_from_db()

        self.assertEqual(self.variant.stock_quantity, 10)
        self.assertFalse(
            StockMovement.objects.filter(
                variant=self.variant,
            ).exists()
        )

        form = mocked_render.call_args.args[2]["form"]

        self.assertFormError(
            form,
            "change_qty",
            "This adjustment would make the stock quantity negative.",
        )

    def test_owner_cannot_adjust_another_shops_variant(self):
        url = reverse(
            "products:variant-stock-adjust",
            kwargs={
                "shop_pk": self.other_shop.pk,
                "product_pk": self.other_product.pk,
                "variant_pk": self.other_variant.pk,
            },
        )

        response = self.client.post(
            url,
            {
                "change_qty": 5,
                "reason": StockMovement.Reason.RESTOCK,
            },
        )

        self.assertEqual(response.status_code, 404)

        self.other_variant.refresh_from_db()

        self.assertEqual(self.other_variant.stock_quantity, 5)
        self.assertFalse(
            StockMovement.objects.filter(
                variant=self.other_variant,
            ).exists()
        )

    def test_archived_variant_cannot_be_adjusted(self):
        self.variant.is_active = False
        self.variant.save(update_fields=["is_active"])

        url = reverse(
            "products:variant-stock-adjust",
            kwargs={
                "shop_pk": self.shop.pk,
                "product_pk": self.product.pk,
                "variant_pk": self.variant.pk,
            },
        )

        response = self.client.post(
            url,
            {
                "change_qty": 5,
                "reason": StockMovement.Reason.RESTOCK,
            },
        )

        self.assertEqual(response.status_code, 404)

        self.variant.refresh_from_db()

        self.assertEqual(self.variant.stock_quantity, 10)
        self.assertFalse(
            StockMovement.objects.filter(
                variant=self.variant,
            ).exists()
        )

    def test_variant_of_archived_product_cannot_be_adjusted(self):
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])

        url = reverse(
            "products:variant-stock-adjust",
            kwargs={
                "shop_pk": self.shop.pk,
                "product_pk": self.product.pk,
                "variant_pk": self.variant.pk,
            },
        )

        response = self.client.post(
            url,
            {
                "change_qty": 5,
                "reason": StockMovement.Reason.RESTOCK,
            },
        )

        self.assertEqual(response.status_code, 404)

        self.variant.refresh_from_db()

        self.assertEqual(self.variant.stock_quantity, 10)
        self.assertFalse(
            StockMovement.objects.filter(
                variant=self.variant,
            ).exists()
        )
    def test_owner_can_view_stock_history_newest_first(self):
        first_movement = StockMovement.objects.create(
            variant=self.variant,
            created_by=self.owner,
            change_qty=5,
            reason=StockMovement.Reason.RESTOCK,
        )
        second_movement = StockMovement.objects.create(
            variant=self.variant,
            created_by=self.owner,
            change_qty=-2,
            reason=StockMovement.Reason.DAMAGE,
        )

        url = reverse(
            "products:variant-stock-history",
            kwargs={
                "shop_pk": self.shop.pk,
                "product_pk": self.product.pk,
                "variant_pk": self.variant.pk,
            },
        )

        with patch(
            "products.views.render",
            return_value=HttpResponse(),
        ) as mocked_render:
            response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        context = mocked_render.call_args.args[2]

        self.assertEqual(context["shop"], self.shop)
        self.assertEqual(context["product"], self.product)
        self.assertEqual(context["variant"], self.variant)
        self.assertEqual(
            list(context["movements"]),
            [second_movement, first_movement],
        )
        self.assertEqual(second_movement.created_by, self.owner)

    def test_owner_cannot_view_another_shops_stock_history(self):
        StockMovement.objects.create(
            variant=self.other_variant,
            created_by=self.other_owner,
            change_qty=3,
            reason=StockMovement.Reason.RESTOCK,
        )

        url = reverse(
            "products:variant-stock-history",
            kwargs={
                "shop_pk": self.other_shop.pk,
                "product_pk": self.other_product.pk,
                "variant_pk": self.other_variant.pk,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_archived_variant_stock_history_returns_404(self):
        self.variant.is_active = False
        self.variant.save(update_fields=["is_active"])

        url = reverse(
            "products:variant-stock-history",
            kwargs={
                "shop_pk": self.shop.pk,
                "product_pk": self.product.pk,
                "variant_pk": self.variant.pk,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_product_detail_displays_low_stock_warning(self):
        self.variant.stock_quantity = 3
        self.variant.low_stock_threshold = 3
        self.variant.save(
            update_fields=[
                "stock_quantity",
                "low_stock_threshold",
            ]
        )

        url = reverse(
            "products:product-detail",
            kwargs={
                "shop_pk": self.shop.pk,
                "product_pk": self.product.pk,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Low stock")

class StockAdjustmentServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="inventory@example.com",
            password="testpass123",
            full_name="Inventory Owner",
            status=User.Status.ACTIVE,
        )

        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Inventory Shop",
            slug="inventory-shop",
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

        self.variant = ProductVariant.objects.create(
            product=self.product,
            color="Black",
            size="M",
            unit_price=Decimal("15.00"),
            currency=ProductVariant.Currency.USD,
            stock_quantity=10,
            low_stock_threshold=3,
        )

    def test_restock_increases_quantity_and_creates_movement(self):
        movement = adjust_variant_stock(
            variant=self.variant,
            change_qty=5,
            reason=StockMovement.Reason.RESTOCK,
            created_by=self.owner,
        )

        self.variant.refresh_from_db()

        self.assertEqual(self.variant.stock_quantity, 15)
        self.assertEqual(movement.variant, self.variant)
        self.assertEqual(movement.change_qty, 5)
        self.assertEqual(movement.reason, StockMovement.Reason.RESTOCK)
        self.assertEqual(movement.created_by, self.owner)

    def test_negative_adjustment_decreases_stock(self):
        movement = adjust_variant_stock(
            variant=self.variant,
            change_qty=-4,
            reason=StockMovement.Reason.DAMAGE,
            created_by=self.owner,
        )

        self.variant.refresh_from_db()

        self.assertEqual(self.variant.stock_quantity, 6)
        self.assertEqual(movement.change_qty, -4)

    def test_adjustment_cannot_make_stock_negative(self):
        with self.assertRaisesMessage(
            ValidationError,
            "This adjustment would make the stock quantity negative.",
        ):
            adjust_variant_stock(
                variant=self.variant,
                change_qty=-11,
                reason=StockMovement.Reason.ADJUSTMENT,
                created_by=self.owner,
            )

        self.variant.refresh_from_db()

        self.assertEqual(self.variant.stock_quantity, 10)
        self.assertFalse(
            StockMovement.objects.filter(variant=self.variant).exists()
        )

    def test_zero_adjustment_is_rejected(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Stock adjustment quantity cannot be zero.",
        ):
            adjust_variant_stock(
                variant=self.variant,
                change_qty=0,
                reason=StockMovement.Reason.ADJUSTMENT,
                created_by=self.owner,
            )

        self.variant.refresh_from_db()

        self.assertEqual(self.variant.stock_quantity, 10)
        self.assertFalse(
            StockMovement.objects.filter(variant=self.variant).exists()
        )

    def test_archived_variant_cannot_be_adjusted(self):
        self.variant.is_active = False
        self.variant.save(update_fields=["is_active"])

        with self.assertRaisesMessage(
            ValidationError,
            "Archived product variants cannot be adjusted.",
        ):
            adjust_variant_stock(
                variant=self.variant,
                change_qty=5,
                reason=StockMovement.Reason.RESTOCK,
                created_by=self.owner,
            )

        self.variant.refresh_from_db()

        self.assertEqual(self.variant.stock_quantity, 10)
        self.assertFalse(
            StockMovement.objects.filter(variant=self.variant).exists()
        )

    def test_invalid_reason_is_rejected(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Invalid stock movement reason.",
        ):
            adjust_variant_stock(
                variant=self.variant,
                change_qty=5,
                reason="INVALID",
                created_by=self.owner,
            )

        self.variant.refresh_from_db()

        self.assertEqual(self.variant.stock_quantity, 10)
        self.assertFalse(
            StockMovement.objects.filter(variant=self.variant).exists()
        )

class StockAdjustmentFormTests(TestCase):
    def setUp(self):
        self.variant = ProductVariant(stock_quantity=10)

    def test_positive_stock_adjustment_is_valid(self):
        form = StockAdjustmentForm(
            data={
                "change_qty": 5,
                "reason": StockMovement.Reason.RESTOCK,
            },
            variant=self.variant,
        )

        self.assertTrue(form.is_valid())

    def test_negative_stock_adjustment_is_valid_when_stock_is_available(self):
        form = StockAdjustmentForm(
            data={
                "change_qty": -4,
                "reason": StockMovement.Reason.DAMAGE,
            },
            variant=self.variant,
        )

        self.assertTrue(form.is_valid())

    def test_zero_stock_adjustment_is_invalid(self):
        form = StockAdjustmentForm(
            data={
                "change_qty": 0,
                "reason": StockMovement.Reason.ADJUSTMENT,
            },
            variant=self.variant,
        )

        self.assertFalse(form.is_valid())
        self.assertFormError(
            form,
            "change_qty",
            "Stock adjustment quantity cannot be zero.",
        )

    def test_adjustment_cannot_make_stock_negative(self):
        form = StockAdjustmentForm(
            data={
                "change_qty": -11,
                "reason": StockMovement.Reason.ADJUSTMENT,
            },
            variant=self.variant,
        )

        self.assertFalse(form.is_valid())
        self.assertFormError(
            form,
            "change_qty",
            "This adjustment would make the stock quantity negative.",
        )

    def test_form_only_allows_manual_movement_reasons(self):
        form = StockAdjustmentForm(variant=self.variant)

        reason_values = [
            value
            for value, label in form.fields["reason"].choices
        ]

        self.assertIn(StockMovement.Reason.RESTOCK, reason_values)
        self.assertIn(StockMovement.Reason.ADJUSTMENT, reason_values)
        self.assertIn(StockMovement.Reason.DAMAGE, reason_values)
        self.assertNotIn(StockMovement.Reason.SALE, reason_values)
        self.assertNotIn(
            StockMovement.Reason.CANCELLATION,
            reason_values,
        )