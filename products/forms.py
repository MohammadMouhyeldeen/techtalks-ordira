from django import forms
from django.db.models import Q

from .models import Category, Product, ProductVariant, StockMovement
from shops.models import DeliveryZone, ShopPaymentMethod

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

class CheckoutForm(forms.Form):
    """Guest checkout shell — fully real/validated, but its valid-POST
    branch only builds a preview payload (see storefront_views.checkout).
    No price/stock validation here; that belongs to the real checkout
    service (orders.services.create_order) once SCRUM-65 merges."""

    customer_name = forms.CharField(
        max_length=150,
        label="Full name",
        widget=forms.TextInput(attrs={"class": "form-input"}),
    )
    customer_phone = forms.CharField(
        max_length=30,
        label="Phone number",
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 70 123 456"}),
    )
    fulfillment_type = forms.ChoiceField(
        choices=[("DELIVERY", "Delivery"), ("PICKUP", "Pickup")],
        widget=forms.RadioSelect(attrs={"class": "fulfillment-choice"}),
    )
    delivery_zone = forms.ModelChoiceField(
        queryset=DeliveryZone.objects.none(),
        required=False,
        label="Delivery area",
        widget=forms.Select(attrs={"class": "form-input"}),
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-input"}),
        label="Delivery address",
    )
    selected_payment_method = forms.ModelChoiceField(
        queryset=ShopPaymentMethod.objects.none(),
        label="Payment method",
        widget=forms.Select(attrs={"class": "form-input"}),
    )
    # ProductVariant.Currency, not Order.Currency — this form has zero
    # import coupling to the orders app.
    currency = forms.ChoiceField(
        choices=ProductVariant.Currency.choices,
        widget=forms.Select(attrs={"class": "form-input"}),
    )

    def __init__(self, *args, shop=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.shop = shop
        self.payment_methods_available = False

        if shop is None:
            return

        self.fields["delivery_zone"].queryset = shop.delivery_zones.filter(
            is_active=True
        )
        payment_methods = shop.payment_methods.filter(enabled=True)
        self.fields["selected_payment_method"].queryset = payment_methods
        self.fields["selected_payment_method"].label_from_instance = (
            lambda obj: obj.get_method_name_display()
        )
        self.fields["selected_payment_method"].empty_label = None
        self.payment_methods_available = payment_methods.exists()

        self.fields["delivery_zone"].label_from_instance = (
            lambda obj: f"{obj.area_name} (+{obj.fee})"
        )
        self.fields["delivery_zone"].empty_label = None

        if not shop.pickup_available:
            self.fields["fulfillment_type"].choices = [("DELIVERY", "Delivery")]

    def clean(self):
        cleaned_data = super().clean()
        if not self.payment_methods_available:
            self.add_error(
                None,
                "No payment methods are currently available for this shop. "
                "Please contact the shop owner.",
            )
            return cleaned_data

        fulfillment_type = cleaned_data.get("fulfillment_type")
        if fulfillment_type == "DELIVERY":
            if not cleaned_data.get("delivery_zone"):
                self.add_error(
                    "delivery_zone",
                    "Select a delivery area.",
                )
            if not cleaned_data.get("address"):
                self.add_error(
                    "address",
                    "Enter a delivery address.",
                )
        return cleaned_data


class StockAdjustmentForm(forms.Form):
    change_qty = forms.IntegerField(
        label="Quantity change",
        help_text=(
            "Use a positive number to add stock or a negative number "
            "to remove stock."
        ),
    )
    reason = forms.ChoiceField(
        choices=[
            (
                StockMovement.Reason.RESTOCK,
                StockMovement.Reason.RESTOCK.label,
            ),
            (
                StockMovement.Reason.ADJUSTMENT,
                StockMovement.Reason.ADJUSTMENT.label,
            ),
            (
                StockMovement.Reason.DAMAGE,
                StockMovement.Reason.DAMAGE.label,
            ),
        ],
    )

    def __init__(self, *args, variant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.variant = variant

    def clean_change_qty(self):
        change_qty = self.cleaned_data["change_qty"]

        if change_qty == 0:
            raise forms.ValidationError(
                "Stock adjustment quantity cannot be zero."
            )

        if (
            self.variant
            and self.variant.stock_quantity + change_qty < 0
        ):
            raise forms.ValidationError(
                "This adjustment would make the stock quantity negative."
            )

        return change_qty
