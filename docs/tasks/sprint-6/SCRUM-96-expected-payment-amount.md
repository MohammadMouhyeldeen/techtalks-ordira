# SCRUM-96 — Record Payment Form Expected Amount

- **Owner:** Reem Saijary
- **Status:** In review
- **Related ticket:** SCRUM-96
- **Branch:** `feature/SCRUM-96-expected-payment-amount`
- **Target branch:** `develop`

## Task objective

Payment is arranged between the customer and merchant through WhatsApp. The merchant then records the received payment manually in Ordira.

Because Ordira requires a full payment, the record-payment form must clearly show the amount that the merchant is expected to receive.

This task improves the form by showing the Order total and customer-selected payment method, prefilling the required amount, and displaying the expected converted amount when the merchant selects another currency.

## Previous behavior

The record-payment form allowed the merchant to select a payment method, amount, and currency.

The amount was initialized from the Order total, but the page did not clearly display:

- The Order total and currency.
- The payment method selected by the customer during checkout.
- The expected amount when the merchant selected the other currency.

This made it harder for the merchant to confirm the correct full-payment amount before submitting the form.

## Implementation

### Order total and checkout payment method

The merchant Order detail page now displays a payment expectation summary above the record-payment form.

The summary shows:

- The Order total.
- The Order currency.
- The payment method selected by the customer during checkout.
- The expected payment amount for the currently selected payment currency.

The payment-method display uses the existing guarded helper so the page can show `Not available` if an Order does not have an accessible selected payment method.

### Initial form values

The record-payment form is initialized with:

- The payment method selected by the customer.
- The full Order total as the payment amount.
- The Order’s currency as the selected payment currency.

This allows the merchant to record a normal same-currency payment without manually copying the Order total into the form.

### Cross-currency expected amount

The server calculates the expected amount in both supported currencies using the Order’s saved `fx_rate_snapshot`.

For a USD Order:

- The expected USD amount is the Order total.
- The expected LBP amount is the Order total multiplied by the FX snapshot.

For an LBP Order:

- The expected LBP amount is the Order total.
- The expected USD amount is the Order total divided by the FX snapshot.

Calculated values are rounded to two decimal places using `ROUND_HALF_UP`.

The expected values are added to the template as data attributes. When the merchant changes the currency field, JavaScript updates:

- The displayed expected payment amount.
- The value of the payment amount field.

The Order’s FX snapshot is used instead of the Shop’s current exchange rate so the expected amount remains consistent with the exchange rate saved when the Order was created.

### Invalid FX snapshot protection

Historical or invalid data may contain an `fx_rate_snapshot` equal to or below zero.

Attempting to convert an LBP Order to USD with a zero FX rate would otherwise raise a `ZeroDivisionError` and cause the Order detail page to return a server error.

The expected-payment calculation now checks for a non-positive FX snapshot before performing a conversion.

When the FX snapshot is zero or below:

- Cross-currency conversion is skipped.
- Only the Order’s original total and currency are returned.
- The Order detail page continues to load normally.

### Payment rules remain unchanged

SCRUM-96 changes only the payment form’s presentation and expected-amount guidance.

It does not change:

- How a Payment is saved.
- The full-payment requirement.
- Same-currency payment validation.
- Cross-currency rounding tolerance.
- Duplicate-payment protection.
- Cancelled-Order protection.
- The Payment `PAID` status rule.

The existing payment service remains responsible for validating and saving the Payment.

## User interface behavior

When the merchant opens an unpaid Order:

1. The page displays the Order total and currency.
2. The page displays the payment method selected by the customer.
3. The payment amount is prefilled with the full Order total.
4. The payment currency is prefilled with the Order currency.
5. If the merchant selects the other currency, the expected converted amount is displayed.
6. The amount field is updated with the converted amount.
7. The merchant can submit the existing record-payment form.

The payment expectation section uses the existing Order-page styling and changes to a single-column layout on smaller screens.

## Automated testing

The dedicated payment test file is:

```text
payments/test_record_payment.py
```

The SCRUM-96 tests verify that:

- The form displays the Order total and currency.
- The form displays the payment method selected by the customer during checkout.
- The payment amount is prefilled with the Order total.
- The payment currency is prefilled with the Order currency.
- The payment method is prefilled with the customer-selected method.
- A USD Order displays the expected LBP amount using the FX snapshot.
- An LBP Order displays the expected USD amount using the FX snapshot.
- A non-positive FX snapshot does not cause the Order detail page to return an error.
- An invalid FX snapshot returns only the Order’s original total and currency.
- Existing payment-recording tests continue to pass.

## Verification

The following commands are used to verify the implementation:

```powershell
python manage.py test payments.test_record_payment
python manage.py test
python manage.py check
python manage.py makemigrations --check --dry-run
git diff --check
```

Verification results:

- All 19 dedicated payment-recording tests passed.
- The complete project test suite passed: 517 tests.
- Django’s system check identified no issues.
- No missing migrations were detected.
- No whitespace errors were found.

## Main files changed

- `orders/views.py`
- `payments/test_record_payment.py`
- `templates/orders/order_detail.html`
- `static/orders/css/orders.css`
- `docs/tasks/sprint-5/SCRUM-78-record-payment.md`
- `docs/tasks/sprint-6/SCRUM-96-expected-payment-amount.md`
- `docs/README.md`

## Dependencies

SCRUM-96 builds on:

- SCRUM-64 for the merchant Order detail page.
- SCRUM-78 for manual full-payment recording.
- The Order’s saved `fx_rate_snapshot` for historical currency conversion.

The feature was developed after the Order-page polish work was available because both tasks modify the merchant Order detail interface.

## Final result

The merchant record-payment form now clearly shows the full amount that must be recorded.

The merchant can see the Order total, currency, and customer-selected payment method before submitting the form. The amount is prefilled in the Order currency and automatically updated when the merchant selects the other supported currency.

Cross-currency guidance uses the Order’s saved FX snapshot, while invalid non-positive FX values are handled safely without changing the existing payment-saving or full-payment validation rules.