'''from django import forms

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
        }'''
import re

from django import forms

from .models import Shop


class ShopSetupForm(forms.ModelForm):

    MAX_LOGO_SIZE = 2 * 1024 * 1024  # 2 MB

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

    def clean_slug(self):
        slug = self.cleaned_data.get("slug", "").strip().lower()

        if Shop.objects.filter(slug__iexact=slug).exists():
            raise forms.ValidationError(
                "A shop with this URL already exists."
            )

        return slug

    def clean_whatsapp(self):
        whatsapp = self.cleaned_data.get("whatsapp", "").strip()

        if not whatsapp:
            return whatsapp

        if whatsapp.startswith("+"):
            whatsapp = whatsapp[1:]

        whatsapp = re.sub(r"[\s\-\(\)]", "", whatsapp)

        if not whatsapp.isdigit() or not 10 <= len(whatsapp) <= 15:
            raise forms.ValidationError(
                "Enter a WhatsApp number with 10 to 15 digits, "
                "including the country code."
            )

        if whatsapp.startswith("0"):
            raise forms.ValidationError(
                "Enter the WhatsApp number with the country code."
            )

        return whatsapp

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")

        if logo and logo.size > self.MAX_LOGO_SIZE:
            raise forms.ValidationError(
                "Logo must be 2 MB or smaller."
            )

        return logo