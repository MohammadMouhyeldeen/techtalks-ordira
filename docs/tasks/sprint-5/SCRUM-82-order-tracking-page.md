# SCRUM-82 — Public Order Tracking Page

**Owner:** Hadi Assi<br>
**Sprint:** Sprint 5<br>
**Date completed:** October 8, 2026<br>
**Status:** Awaiting review<br>
**Related ticket:** SCRUM-82<br>
**Branch:** `feature/SCRUM-82-order-tracking-page`<br>
**Pull request:** Add the pull-request link<br>
**Target branch:** `develop`

## Task objective

Let a customer follow their order from a private link after checkout, without needing to message the shop — showing the order's status, items, totals, and payment status.

## Why this task was needed

Before this task, `order_success` was the only page a customer ever saw, and it's reached once, right after checkout, via a one-time session payload. There was no page a customer could return to later (or share a link to) to check whether their order moved past "New," or why it was cancelled if it was. This directly depended on SCRUM-81 (real orders) having merged, since there was nothing real to track before that.

## Requirements

- Route `/store/<shop-slug>/track/<uuid:tracking_token>/`; looked up by `tracking_token` + shop, never by id.
- Shows order number, status (with the five real statuses), the cancellation reason when cancelled, items from the snapshots, delivery fee, total and currency, fulfillment type, and payment status (gracefully absent until SCRUM-78 records one).
- A wrong token, or a token looked up under another shop's slug, 404s — no other customer's data is ever revealed.
- Linked from the order-success page.
- Still renders correctly when a variant was deactivated or a delivery zone deleted (reads only the order's own snapshots).

## Implementation

### Models and database

No model changes or migrations were required. Uses the already-existing `Order`/`OrderItem` snapshot fields and reads `payments.Payment` (already migrated, from SCRUM-78's schema) defensively — no Payment row exists for most orders yet since the service that creates one isn't merged, and the page accounts for that.

### Business logic

- **`orders/views.py::track_order`** (new) — `@public_shop_required`, looks up the order by `tracking_token` + `shop` exactly like `order_success` does, for the same reason: a sequential pk would let anyone enumerate other customers' orders.
- **`orders/views.py::_order_context`** (new, shared helper) — builds the context both `order_success` and `track_order` need (`order_items`, `payment_method_display`, `payment`). `payment` is read via `getattr(order, "payment", None)` rather than `order.payment` directly — Django's reverse one-to-one accessor raises `Payment.DoesNotExist` (deliberately a subclass of `AttributeError`) when no row exists, which is exactly what `getattr`'s default is for, so this already "just works" once SCRUM-78 starts creating `Payment` rows, with zero further code changes needed here.

### Forms and validation

Not applicable — no form on this page.

### Views and URLs

- **`config/urls.py`** — new `store/<slug:shop_slug>/track/<uuid:tracking_token>/` route, named `track_order`, flat and unnamespaced like every other storefront route.

### Templates and styling

- **`templates/storefront/_order_overview.html`** (new, shared partial) — the fulfillment/customer/payment-status sections plus the itemized totals, extracted out of `order_success.html` so both it and the new tracking page render identically from the same data and can never drift apart. Reads only snapshot fields (`zone_name_snapshot`, `address_snapshot`, `product_name_snapshot`, etc.) — never `order.delivery_zone.area_name` or `item.variant.name` directly — so it still renders correctly if the zone was deleted or the variant deactivated.
- **`templates/storefront/order_tracking.html`** (new) — its own hero: a colored status pill (new/preparing/handed-to-delivery/completed/cancelled, each a distinct color), the order number and placed-on date, and the cancellation reason box when the order is cancelled. Includes the shared `_order_overview.html` for the rest.
- **`templates/storefront/order_success.html`** — now includes the same shared partial instead of duplicating the markup, and gained a "Track your order" button next to "Back to shop," linking to the new page.
- **`static/storefront/css/storefront.css`** — `.status-pill` (one color per status group), `.cancellation-box`, `.order-tracking-hero`, and `.order-success-page__actions` (replacing the old single-button CTA class now that there are two buttons).

## Security and data isolation

- `track_order` resolves the order the same way `order_success` does: `get_object_or_404(Order, tracking_token=tracking_token, shop=shop)` — an unknown token 404s, and a real token looked up under a *different* shop's slug also 404s, since the query requires both to match.
- `tracking_token` is an unguessable UUID (already on the model from SCRUM-71), never a sequential id.
- The page only ever reads the requesting order's own fields — there's no way to pivot from one order to another shop's data through this view.

## Automated testing

**`orders/tests.py::OrderTrackingViewTests`** (new, 8 tests):
- A valid token shows the real order's number, items, and customer name.
- An unknown token 404s.
- A real token looked up under a different shop's slug 404s.
- A cancelled order (via the real `cancel_order` service) shows its cancellation reason.
- A deactivated variant (the realistic case — the variant can't be deleted outright while `on_delete=PROTECT` on `OrderItem.variant` protects it) still renders the item correctly from its snapshot.
- A deleted delivery zone still renders the zone name and address from the order's own snapshot.
- No `Payment` row yet shows "Not recorded yet" rather than erroring.
- The order-success page contains a working link to the tracking page for that exact order.

## Manual verification

- Live walkthrough against the dev server: placed a real order on the seeded `demo-fashion` shop, followed the "Track your order" link from the success page, and confirmed the tracking page shows the correct status pill ("New Order"), the real customer name and items, and "Not recorded yet" for payment status.

## Verification results

```powershell
python manage.py check
python manage.py test products.test_cart orders
python manage.py test
```

- Django's system check identified no issues.
- `products.test_cart` + `orders`: **71 tests passed.**
- Complete test suite: **414 tests passed.**

## Files changed

- `orders/views.py`
- `orders/tests.py`
- `config/urls.py`
- `templates/storefront/_order_overview.html` (new)
- `templates/storefront/order_tracking.html` (new)
- `templates/storefront/order_success.html`
- `static/storefront/css/storefront.css`

## Dependencies

- Depends on SCRUM-81 (real orders must exist) — merged.
- Reads `payments.Payment` defensively; shows "Not recorded yet" until SCRUM-78 (record payment) merges and starts creating rows — no further code change needed here when it does.

## Known limitations or follow-up work

- Payment status will read as "Not recorded yet" for every order until SCRUM-78 merges — expected, not a bug.

## Final result

A customer can now follow their order from a private, unguessable link reachable right after checkout or revisited any time later — seeing its current status (including why it was cancelled, if it was), its items and totals from the order's own snapshots, and its payment status once that exists. Verified by 8 new passing tests plus the existing order/checkout suite, and a live walkthrough of the full checkout → success → tracking flow.
