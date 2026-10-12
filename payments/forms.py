from django import forms

from shops.models import ShopPaymentMethod

from .models import Payment


class RecordPaymentForm(forms.Form):
    method = forms.ModelChoiceField(
        queryset=ShopPaymentMethod.objects.none(),
        empty_label="Select a payment method",
    )
    amount = forms.DecimalField(
        min_value=0.01,
        max_digits=15,
        decimal_places=2,
    )
    currency = forms.ChoiceField(
        choices=Payment.Currency.choices,
    )
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Optional payment note",
            }
        ),
    )

    def __init__(self, *args, shop, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["method"].queryset = (
            ShopPaymentMethod.objects
            .filter(shop=shop, enabled=True)
            .order_by("method_name")
        )
