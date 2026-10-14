# SCRUM-89 — Order Success Page With the WhatsApp Button

**Owner:** Hadi Assi<br>
**Sprint:** Sprint 6<br>
**Date completed:** October 14, 2026<br>
**Status:** Awaiting review<br>
**Related ticket:** SCRUM-89 (Epic SCRUM-74)<br>
**Branch:** `feature/SCRUM-89-whatsapp-payment-button`<br>
**Pull request:** Add the pull-request link<br>
**Target branch:** `develop`

## Task objective

After the system auto-confirms an order, send the customer to an empty WhatsApp chat with the seller to arrange payment — no prefilled text, no change to order creation/confirmation itself.

## Why this task was needed

Order creation already confirms itself (`create_order`, from Sprint 5). The order-success page showed the order summary and a tracking link, but gave the customer no way to actually reach the seller to pay. This ticket adds that last step of the flow.

## What the success page already did (kept as-is)

Read `templates/storefront/order_success.html` and `orders/views.py::order_success`/`_order_context` before changing anything: the page already renders the order via `_order_overview.html` (fulfillment, customer, payment-method name, payment status, itemized totals) and already links to `track_order`. None of that changed — order creation/confirmation and the tracking link are untouched.

## Implementation

### Business logic

- **`orders/views.py::_shop_whatsapp_link(shop)`** (new) — strips everything but digits from `shop.whatsapp` and returns `https://wa.me/<digits>`, or `None` if nothing is left. `ShopContactLogoCleanMixin.clean_whatsapp` (shops/forms.py) already normalizes this to digits-only, no leading `0`, when a merchant saves it through the settings form — but the real dev data has at least one shop stored with a leading `+` (likely seeded before that validation existed), so this strips again at render time rather than trusting every row was written the clean way.
- `order_success` passes `"whatsapp_link": _shop_whatsapp_link(shop)` into the template context, built from the `shop` the view already resolved via `@public_shop_required` (slug in the URL) and the same `shop=shop` filter used to look up the order — so it's structurally impossible for this to be a different shop's number than the order's own.
- `track_order` / `_order_context` (shared with the tracking page) are untouched — the WhatsApp CTA is success-page-only, per the ticket.

### Templates and styling

- **`templates/storefront/order_success.html`**:
  - The order number is now its own large, bold line (`.order-success-hero__number`) instead of being folded into a small sentence with the status.
  - New `.order-success-page__whatsapp` block: the primary "Contact the seller on WhatsApp to arrange payment" button when `whatsapp_link` is set, or a plain-text "contact the shop directly" message when it isn't — never both, never neither, no exception path.
  - "Back to shop" demoted from `.btn-primary` to the existing `.btn-ghost` class so the WhatsApp button is the single clear primary CTA now that there are three buttons/messages on the page.
  - `extra_js` gained a `setTimeout(..., 3000)` that navigates the page to the same `whatsapp_link` — only emitted when a link exists. The button itself is unconditional inside that same `{% if %}`, so it's always there as the fallback regardless of whether the redirect fires, is blocked, or WhatsApp isn't installed.
- **`templates/storefront/base_public.html`** — added an `i-whatsapp` icon symbol (same sprite pattern as the `i-copy` icon added for SCRUM-83).
- **`static/storefront/css/storefront.css`** — `.order-success-hero__number`/`__status`, `.order-success-page__whatsapp` (+ its `.btn` override to allow wrapping and cap width, since the button's label is long enough to overflow at 360–390px with the base `.btn`'s `white-space:nowrap`), `.order-success-page__no-whatsapp`. Added `.order-success-page__whatsapp` to the shared `fade-up-in` entrance animation and its `prefers-reduced-motion` override list.

## Security and data isolation

The WhatsApp number always comes from the `shop` object the view already resolved for this exact order (`get_object_or_404(Order..., shop=shop)`), never looked up separately — there is no code path where another shop's `whatsapp` could end up in this order's context.

## Automated testing

**`orders/tests.py::OrderSuccessWhatsAppTests`** (new, 4 tests):
- The link contains the shop's digits as `https://wa.me/<digits>` and the page never contains `text=`.
- Two shops with different numbers: each order's success page contains only its own shop's link, never the other's.
- A shop with an empty `whatsapp` renders 200, with no `wa.me` anywhere on the page and the "contact the shop directly" copy present instead.
- The order already exists in the database (by `pk`) both before and after the success page is requested — confirming the WhatsApp feature didn't change when/whether the order is persisted.

## Manual verification

- `python manage.py test orders` and the full suite (counts below) pass, including against a shop whose `whatsapp` is stored as `+96170123456` (real seed data, confirming the digit-stripping guard isn't just defensive theater).
- Live dev-server click-through was blocked by a **pre-existing, unrelated** issue on this machine's local dev database: `customers.0002_normalize_existing_customer_phones` fails to migrate because of a bad legacy phone number already in the dev DB (`Customer pk=3, phone='123456'`), which in turn leaves `payments.0002_payment_note` unapplied, which 500s *any* order-success/tracking page (not just this ticket's change) the moment it touches `order.payment` via `_order_context`. Confirmed via `showmigrations` that the failed `migrate` attempt rolled back cleanly (no partial schema change) and left the dev DB exactly as it was. Did not touch that customer row or anyone else's migration to work around it — flagging it instead since it blocks local `runserver` testing for everyone until someone corrects or removes that row.

## Verification results

```powershell
python manage.py check
python manage.py test orders -v2
python manage.py test
```

- Django's system check identified no issues.
- `orders`: **72 tests passed.**
- Complete test suite: **483 tests passed.**

## Files changed

- `orders/views.py`
- `orders/tests.py`
- `templates/storefront/order_success.html`
- `templates/storefront/base_public.html`
- `static/storefront/css/storefront.css`

## Dependencies

- Depends on nothing (per the sprint plan) — built directly on top of Sprint 5's merged order flow.

## Known limitations or follow-up work

- The dev-database migration blocker described above is pre-existing and outside this ticket's scope; someone needs to decide how to handle `Customer pk=3`'s invalid phone number before `payments.0002_payment_note` (and anything after it) can be applied locally.
- `shop.whatsapp` is still optional (`blank=True`) on this branch — SCRUM-90 (Jinan) makes it required; this ticket's "no WhatsApp number" fallback stays relevant for any shop created before that lands.

## Final result

The order-success page now shows the order number large and prominent, keeps the existing order summary and tracking link, and gives the customer a primary "Contact the seller on WhatsApp to arrange payment" button that opens an empty chat with the order's own shop — auto-redirecting there after ~3 seconds while leaving the button as a permanent fallback, and degrading to a plain "contact the shop directly" message with no crash when the shop has no WhatsApp number set.
