from django import forms

from .models import Shop


class ShopSetupForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = (
            "name",
            "slug",
            "whatsapp",
            "instagram",
            "logo",
            "pickup_available",
            "exchange_rate_lbp_per_usd",
        )
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "Enter your shop name",
                }
            ),
            "slug": forms.TextInput(
                attrs={
                    "placeholder": "your-shop-name",
                }
            ),
            "whatsapp": forms.TextInput(
                attrs={
                    "placeholder": "e.g. +961 70 123 456",
                }
            ),
            "instagram": forms.TextInput(
                attrs={
                    "placeholder": "@yourshop",
                }
            ),
            "exchange_rate_lbp_per_usd": forms.NumberInput(
                attrs={
                    "placeholder": "e.g. 89500.00",
                    "step": "0.01",
                    "min": "0.01",
                }
            ),
        }