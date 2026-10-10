from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from orders.models import Order

from .forms import RecordPaymentForm
from .services import record_payment


@login_required
@require_POST
def record_order_payment(request, shop_pk, order_pk):
    order = get_object_or_404(
        Order.objects.select_related("shop"),
        pk=order_pk,
        shop_id=shop_pk,
        shop__owner=request.user,
    )

    form = RecordPaymentForm(
        request.POST,
        shop=order.shop,
    )

    if form.is_valid():
        try:
            record_payment(
                order=order,
                method=form.cleaned_data["method"],
                amount=form.cleaned_data["amount"],
                currency=form.cleaned_data["currency"],
                note=form.cleaned_data["note"],
            )
        except ValidationError as error:
            messages.error(
                request,
                " ".join(error.messages),
            )
        else:
            messages.success(
                request,
                "Payment recorded successfully.",
            )
    else:
        error_messages = []

        for errors in form.errors.values():
            error_messages.extend(errors)

        messages.error(
            request,
            " ".join(error_messages),
        )

    return redirect(
        "orders:order-detail",
        shop_pk=shop_pk,
        order_pk=order_pk,
    )
