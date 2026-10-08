# SCRUM-84 — Guard Against a Missing Payment Method on Order Pages

**Owner:** Hadi Assi<br>
**Sprint:** Sprint 5<br>
**Date completed:** October 8, 2026<br>
**Status:** Awaiting review<br>
**Related ticket:** SCRUM-84<br>
**Branch:** `feature/SCRUM-84-payment-method-null-guard`<br>
**Pull request:** Add the pull-request link<br>
**Target branch:** `develop`

## Task objective

Stop the order-success page (and any other template that prints a payment method) from crashing if `order.selected_payment_method` is ever missing — show "Not available" instead of a 500.

## Why this task was needed

`orders/views.py::order_success` called `order.selected_payment_method.get_method_name_display()` directly. If that attribute were ever unset, this raises before the template even renders, returning a 500 to a real customer instead of a usable page.

## A discrepancy worth recording

The ticket assumes a shop can delete a payment method out from under a placed order. In the current schema that can't happen: `Order.selected_payment_method` is `on_delete=PROTECT` **and** `null=False` (`orders/models.py:42`) — Postgres itself refuses both the deletion (FK protect) and a `NULL` in that column (`NOT NULL`). The merchant payment-method settings page (SCRUM-79) doesn't delete rows either; it only flips `enabled` via `update_or_create` (`shops/forms.py::PaymentMethodSettingsForm.save`), so there is no code path today that produces this state. This is the same kind of mismatch already hit on SCRUM-82 (`OrderItem.variant` is PROTECT, not actually deletable either) — handled the same way: add the guard anyway since it's cheap insurance, and prove it with the closest reachable equivalent instead of the literal (currently impossible) scenario.

## Implementation

### Business logic

- **`orders/views.py::_payment_method_display(order)`** (new, shared helper) — returns `"Not available"` when the order has no payment method, else `method.get_method_name_display()`. Reads the FK via `getattr(order, "selected_payment_method", None)` rather than a plain truthiness check: Django's forward-FK descriptor raises `RelatedObjectDoesNotExist` (deliberately a subclass of both the target model's `DoesNotExist` and `AttributeError`) when the id is unset on a non-nullable FK, so a bare `order.selected_payment_method` would itself raise — `getattr`'s default is exactly what absorbs that.
- `order_success` now builds `payment_method_display` through this helper instead of calling the accessor inline.

### Templates

- **`templates/orders/order_detail.html`** (merchant-facing order detail, SCRUM-64) — wrapped the payment method cell in `{% if order.selected_payment_method %}...{% else %}Not available{% endif %}`. This one was never going to 500 (Django templates swallow `AttributeError` on a dotted lookup and render it as empty), but it would have silently shown a blank "Method" row instead of the required "Not available" copy.
- `templates/storefront/order_success.html` needed no change — it already rendered `payment_method_display` from context, so fixing the view fixes this page.

## Automated testing

- **`orders/tests.py::OrderSuccessViewTests`** (2 new tests):
  - A real checked-out order's payment method still displays its real name ("Cash") — regression guard for the refactor.
  - `_payment_method_display` returns "Not available" for an order whose `selected_payment_method` was cleared in memory (never saved — the DB would reject a real `NULL` write here, per the discrepancy above).
- **`orders/test_merchant_orders.py::MerchantOrderViewTests`** (1 new test):
  - `templates/orders/order_detail.html` renders "Not available" (via `render_to_string` against an in-memory-mutated order) instead of a blank cell or an error.

## Verification results

```powershell
python manage.py check
python manage.py test orders -v2
python manage.py test
```

- Django's system check identified no issues.
- `orders`: **37 tests passed.**
- Complete test suite: **422 tests passed.**

## Files changed

- `orders/views.py`
- `orders/tests.py`
- `orders/test_merchant_orders.py`
- `templates/orders/order_detail.html`

## Dependencies

- Depends on SCRUM-81 (the success page lives on `develop` now that PR #51 merged) — merged.

## Known limitations or follow-up work

- The guarded state (`selected_payment_method` missing) can't currently occur through any real user action — it's defensive-only until/unless the model's `on_delete`/nullability or the merchant settings page's behavior changes.

## Final result

Both the customer-facing order-success page and the merchant order-detail page now show "Not available" instead of crashing or rendering blank if an order's payment method is ever missing, with the shared display logic unit-tested directly against that state.
