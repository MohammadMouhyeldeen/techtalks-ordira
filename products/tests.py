from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import User
from shops.models import Shop

from .forms import CategoryForm, ProductForm, ProductVariantForm
from .models import Category, Product, ProductVariant


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