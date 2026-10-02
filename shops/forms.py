import re

from django import forms

from .models import Shop, Subscription


class ShopContactLogoCleanMixin:
    """Shared whatsapp/logo validation for ShopSetupForm and ShopSettingsForm."""

    MAX_LOGO_SIZE = 2 * 1024 * 1024  # 2 MB

    def clean_whatsapp(self):
        whatsapp = self.cleaned_data.get("whatsapp", "").strip()

        if not whatsapp:
            return whatsapp

        if whatsapp.startswith("+"):
            whatsapp = whatsapp[1:]

        whatsapp = re.sub(r"[\s\-\(\)\[\]]", "", whatsapp)

        if (not whatsapp.isdigit() or not whatsapp.isascii() or not 10 <= len(whatsapp) <= 15):
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


class ShopSetupForm(ShopContactLogoCleanMixin, forms.ModelForm):

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


class ShopSettingsForm(ShopContactLogoCleanMixin, forms.ModelForm):

    class Meta:

        model = Shop

        fields = (
            "name",
            "whatsapp",
            "instagram",
            "logo",
            "pickup_available",
        )

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "Enter your shop name",
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
        }

class SubscriptionForm(forms.ModelForm):
    def __init__(self, *args, shop=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.shop = shop

    class Meta:
        model = Subscription
        fields = [
            "plan",
            "status",
            "starts_on",
            "ends_on",
        ]
        widgets = {
            "starts_on": forms.DateInput(
                attrs={"type": "date"}
            ),
            "ends_on": forms.DateInput(
                attrs={"type": "date"}
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        starts_on = cleaned_data.get("starts_on")
        ends_on = cleaned_data.get("ends_on")
        status = cleaned_data.get("status")

        if starts_on and ends_on and ends_on < starts_on:
            raise forms.ValidationError(
                "End date cannot be before start date."
            )

        if (
            self.shop
            and status == Subscription.Status.ACTIVE
        ):
            active_subscriptions = Subscription.objects.filter(
                shop=self.shop,
                status=Subscription.Status.ACTIVE,
            )

            if self.instance.pk:
                active_subscriptions = active_subscriptions.exclude(
                    pk=self.instance.pk
                )

            if active_subscriptions.exists():
                raise forms.ValidationError(
                    "This shop already has an active subscription."
                )

        return cleaned_data
