# SCRUM-78 — Record Payment

**Owner:** Reem Saijary
**Sprint:** Sprint 5
**Date completed:** October 9, 2026
**Status:** Ready for review
**Related ticket:** SCRUM-78
**Branch:** `feature/SCRUM-78-record-payment`
**Target branch:** `develop`

## Task objective

The purpose of SCRUM-78 was to allow a Shop Owner to manually record a payment for an Order from the merchant Order detail page.

Ordira does not process money automatically. Instead, the Shop Owner confirms that payment was received and records:

- The payment method
- The received amount
- The payment currency
- An optional note

After a payment is recorded, the merchant Order detail page and the customer’s public tracking page display the updated payment information.

## Payment model update

Added an optional `note` field to the existing `Payment` model:

```python
note = models.TextField(blank=True)
```

The note allows the Shop Owner to store additional information such as:

- Cash received at the shop
- Whish transaction details
- Bank-transfer reference
- Other payment-related comments

The following migration was created:

```text
payments/migrations/0002_payment_note.py
```

No other database model changes were required.

## Payment recording service

Created `payments/services.py` to keep payment business logic separate from forms and views.

The `record_payment()` service:

1. Locks the selected Order using `select_for_update()`.
2. Verifies that the Order has not already received a payment.
3. Rejects payments for cancelled Orders.
4. Confirms that the selected payment method belongs to the Order’s Shop.
5. Confirms that the selected payment method is enabled.
6. Validates the payment amount and currency.
7. Converts the amount to the Order’s currency when necessary.
8. Rejects a payment whose converted value exceeds the Order total.
9. Creates the Payment with a `PAID` status.
10. Records the date and time in `received_at`.

The operation runs inside a database transaction to prevent duplicate or inconsistent payment records.

## Duplicate-payment protection

The Payment model has a one-to-one relationship with Order.

This means that an Order can have only one Payment record in the current MVP workflow.

The service also checks for an existing payment while the Order is locked. If a payment was already recorded, a second attempt is rejected with a validation error.

This protects the system if two payment requests are submitted at nearly the same time.

## Currency conversion

Payments may be entered in USD or LBP.

When the payment currency differs from the Order currency, the service converts the amount using the exchange-rate snapshot saved on the Order.

Using `fx_rate_snapshot` is important because it preserves the exchange rate that applied when the Order was created. Later changes to the Shop’s current exchange rate do not change the meaning of an existing Order or Payment.

The converted value is saved in:

```text
amount_in_order_currency
```

For example, if an Order total is `15.00 USD` and its exchange-rate snapshot is `90000 LBP` per USD, a payment of `1350000 LBP` is stored as:

```text
amount = 1350000.00
currency = LBP
amount_in_order_currency = 15.00
```

## Payment method snapshot

The service saves the selected payment method’s display name in:

```text
method_name_snapshot
```

This preserves the payment method shown on the historical Payment even if the Shop’s payment-method settings change later.

## Payment form

Created `payments/forms.py` containing `RecordPaymentForm`.

The form accepts:

- `method`
- `amount`
- `currency`
- `note`

The available payment-method choices are restricted to enabled methods belonging to the selected Shop.

This prevents a Shop Owner from selecting:

- A disabled payment method
- A payment method belonging to another Shop

The service repeats the important validations so that security does not depend only on the form.

## Merchant payment view

Implemented an authenticated and owner-scoped payment-recording view in `payments/views.py`.

The view:

- Accepts `POST` requests only.
- Verifies that the selected Shop belongs to the logged-in owner.
- Verifies that the Order belongs to that Shop.
- Validates the submitted form.
- Calls the payment-recording service.
- Displays validation errors safely.
- Redirects back to the merchant Order detail page after success.

A Shop Owner attempting to access another Shop’s Order receives a `404 Not Found` response.

Using `404` protects cross-shop data by avoiding confirmation that another Shop’s resource exists.

## URL routing

Created `payments/urls.py` with the named payment-recording route.

The payment URLs were included in the main project URL configuration.

The route uses both `shop_pk` and `order_pk` so ownership can be checked before recording the Payment.

## Merchant Order detail integration

Updated the merchant Order detail page to display the Payment section.

When no Payment exists and the Order is eligible, the page displays the payment-recording form.

The form allows the merchant to choose an enabled payment method, enter the received amount and currency, and provide an optional note.

After a Payment is recorded, the page displays the saved payment information instead of the form, including:

- Payment status
- Payment method snapshot
- Original amount and currency
- Amount in the Order currency
- Received date
- Optional note

Cancelled Orders cannot receive payments and do not display an active recording form.

## Public tracking integration

The shared public Order overview was updated so the customer can see the current payment status.

The Order success page and public tracking page use the same shared template:

```text
templates/storefront/_order_overview.html
```

The customer sees:

- `Unpaid` when no Payment record exists.
- `Paid` after the Shop Owner records the Payment.
- The payment received date when available.

Only the payment status and received date are exposed publicly. Merchant-only form controls and private notes are not displayed on the public tracking page.

## Access control and validation

The implementation protects the payment workflow at multiple levels.

It verifies that:

- The merchant is authenticated.
- The Shop belongs to the logged-in owner.
- The Order belongs to that Shop.
- The payment method belongs to the same Shop.
- The payment method is enabled.
- The amount is valid and greater than zero.
- The currency is supported.
- The converted amount does not exceed the Order total.
- The Order is not cancelled.
- A Payment has not already been recorded.

These checks prevent cross-shop access, duplicate records, disabled-method usage, overpayments, and payments on cancelled Orders.

## Automated testing

A dedicated test file was created:

```text
payments/test_record_payment.py
```

The payment tests verify:

- A valid Payment can be recorded.
- The Payment receives a `PAID` status.
- The received timestamp is saved.
- The payment-method snapshot is saved.
- The optional note is saved.
- Payments can be converted between USD and LBP.
- Overpayments are rejected.
- Duplicate Payments are rejected.
- Cancelled Orders cannot receive Payments.
- A non-owner receives a `404` response.
- The payment endpoint accepts `POST`.
- The payment endpoint rejects `GET`.
- The public tracking page shows `Unpaid` before payment.
- The public tracking page shows `Paid` after payment is recorded.

The existing Order tracking test was also updated to expect the new `Unpaid` wording.

## Verification results

The following checks were completed successfully:

```powershell
python manage.py test payments.test_record_payment
python manage.py test
python manage.py check
python manage.py makemigrations --check --dry-run
git diff --check
```

Results:

- All 10 dedicated payment-recording tests passed.
- The complete project test suite passed: 437 tests.
- Django’s system check identified no issues.
- No missing migrations were detected.
- No whitespace errors were found.

## Main files changed

- `config/urls.py`
- `orders/views.py`
- `orders/tests.py`
- `payments/forms.py`
- `payments/models.py`
- `payments/services.py`
- `payments/views.py`
- `payments/urls.py`
- `payments/test_record_payment.py`
- `payments/migrations/0002_payment_note.py`
- `templates/orders/order_detail.html`
- `templates/storefront/_order_overview.html`
- `static/orders/css/orders.css`
- `docs/tasks/sprint-5/SCRUM-78-record-payment.md`
- `docs/README.md`

## Dependencies

SCRUM-78 depends on:

- SCRUM-65 for the Order checkout service and saved Order totals.
- SCRUM-64 for the merchant Order detail page.
- SCRUM-82 for the public Order tracking page.

The feature was rebased onto the latest `develop` branch after the required Order list, detail, and tracking work was merged.

## Final result

Ordira now supports owner-scoped manual payment recording.

A Shop Owner can record a received payment directly from the merchant Order detail page. The system validates ownership, payment method, amount, currency, Order status, and duplicate submissions before saving the Payment.

Currency conversion uses the Order’s saved exchange-rate snapshot, historical payment-method information is preserved, and customers can see an accurate `Paid` or `Unpaid` status through the public Order tracking page.
