from django import forms
from django.db.models import Q

from .models import Category, Product, ProductVariant


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name"]

    def __init__(self, *args, shop=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.shop = shop

    def clean_name(self):
        name = self.cleaned_data["name"].strip()

        if self.shop:
            categories = Category.objects.filter(
                shop=self.shop,
                name__iexact=name,
            )

            if self.instance.pk:
                categories = categories.exclude(pk=self.instance.pk)

            if categories.exists():
                raise forms.ValidationError(
                    "A category with this name already exists in your shop."
                )

        return name


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name",
            "description",
            "image",
            "category",
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, shop=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.shop = shop

        if shop is None:
            self.fields["category"].queryset = Category.objects.none()
            return

        category_filter = Q(is_active=True)

        # Keep the current archived category available while editing.
        if self.instance.pk and self.instance.category_id:
            category_filter |= Q(pk=self.instance.category_id)

        self.fields["category"].queryset = Category.objects.filter(
            category_filter,
            shop=shop,
        )

    def clean_category(self):
        category = self.cleaned_data["category"]

        if self.shop and category.shop_id != self.shop.id:
            raise forms.ValidationError(
                "The selected category does not belong to your shop."
            )

        return category


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = [
            "color",
            "size",
            "unit_price",
            "currency",
            "stock_quantity",
            "low_stock_threshold",
        ]

    def __init__(self, *args, product=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.product = product

    def clean(self):
        cleaned_data = super().clean()

        color = cleaned_data.get("color", "").strip()
        size = cleaned_data.get("size", "").strip()

        cleaned_data["color"] = color
        cleaned_data["size"] = size

        if self.product and color and size:
            variants = ProductVariant.objects.filter(
                product=self.product,
                color__iexact=color,
                size__iexact=size,
            )

            if self.instance.pk:
                variants = variants.exclude(pk=self.instance.pk)

            if variants.exists():
                raise forms.ValidationError(
                    "This color and size combination already exists "
                    "for this product."
                )

        return cleaned_data