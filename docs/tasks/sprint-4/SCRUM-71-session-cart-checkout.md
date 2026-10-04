# SCRUM-71 — Session Cart + Checkout/Order-Success Shells

**Owner:** Hadi Assi<br>
**Sprint:** Sprint 4<br>
**Date completed:** October 2, 2026<br>
**Status:** Awaiting review<br>
**Related ticket:** SCRUM-71<br>
**Branch:** `feature/SCRUM-71-session-cart-checkout`<br>
**Pull request:** https://github.com/MohammadMouhyeldeen/techtalks-ordira/pull/43<br>
**Target branch:** `develop`

## Task objective

Build a real, fully-working session-backed shopping cart for the guest storefront (add/update/remove variant lines, quantity, subtotal), plus checkout and order-success page shells that complete the guest ordering flow end-to-end (Cart → Checkout → Order) for demo and review purposes.

The cart half has no blockers — it only needs the existing `ProductVariant` model. The checkout/order-success half is intentionally a shell: it does not yet call a real order-creation service, because that service (`orders.services.create_order`, SCRUM-65) was still on a teammate's unmerged branch at the time of this work.

## Why this task was needed

Sprint 4's goal is a guest checkout flow. Before this task, the storefront had a catalog and product detail page (SCRUM-46/SCRUM-52) but no way to actually collect items or move toward an order — "Add to Cart" buttons were cosmetic only (a local button-state change and a toast, with an explicit code comment documenting that there was no real cart, no persistence, and no shared state between pages).

Without this task, the rest of Sprint 4's checkout work (SCRUM-65's order-creation service, Mohammad's merchant order views, Jinan's status transitions) would have nothing to demo against on the customer-facing side, and the three other people depending on SCRUM-65 would have no checkout UI to wire real submission into once it merges.

## Requirements

- Session-backed cart: add/update/remove variant lines, quantity, subtotal.
- Checkout form template and order-success page.
- Build the shells/markup now; wire real submission once SCRUM-65 (checkout service) merges.
- Markup/session-state only — no price/stock validation logic here; that belongs to the real checkout service.

## Implementation

### Models and database

No model changes or database migrations were required. The cart is session-only (no new table). `Order`/`OrderItem`, `Customer`, `DeliveryZone`, and `ShopPaymentMethod` were all already present and migrated on `develop` from earlier schema work — this task only adds the service-less preview pages around them.

### Business logic

- **`products/cart.py`** (new) — the session cart itself. Storage shape is `request.session["cart"] = {"<shop_id>": {"<variant_id>": quantity}}`, nested by shop so a browser session visiting two different shops keeps separate carts. Functions: `add_item`, `update_item` (quantity ≤ 0 removes the line), `remove_item`, `get_lines`, `get_item_count`, `get_totals`, `get_raw_count`, `clear`.
  `get_lines` resolves variants fresh against the database on every call (`is_active=True`, `product__is_active=True`, scoped to the shop), and silently prunes any session entry that no longer resolves (deleted/deactivated variant, or a variant belonging to a different shop) — both from the returned result and from the session itself, so a dead reference isn't carried forever. `get_totals` keeps USD and LBP subtotals separate rather than mixing currencies. No stock or price validation lives here by design — that's the real checkout service's job.
- **Checkout's "Place Order" does not create any `Order`/`OrderItem` row.** On a valid submission, `storefront_views.checkout` builds a JSON-serializable preview payload from the real cleaned form data and the real cart lines — summing line totals, adding the delivery fee, and converting currency via `shop.exchange_rate_lbp_per_usd` using the same USD↔LBP formula the real service will use — and stashes it as `request.session["checkout_preview"]`. The cart itself is **not** cleared, since nothing real happened yet.
- **`orders/views.py::order_success_preview`** (new) pops that preview from the session (one-time — a reload or a direct/bookmarked visit falls back to a generic static example order) and builds real, unsaved `Order`/`OrderItem` model instances to render (never `.save()`d, so no DB write). Using the real model classes means `get_status_display()`/`get_fulfillment_type_display()` work for free, and the template needs zero changes when this is later swapped for a real queried `Order`. The swap-in point is documented inline in the module.

### Forms and validation

- **`products/forms.py::CheckoutForm`** — a plain `forms.Form` (not a `ModelForm`), constructor takes `shop=` the same way `ProductForm`/`CategoryForm` already do. Fields: `customer_name`, `customer_phone`, `fulfillment_type` (Delivery/Pickup), `delivery_zone`, `address`, `selected_payment_method`, `currency`.
  `delivery_zone` and `selected_payment_method` querysets are scoped to the shop's active zones / enabled payment methods, with their blank "---------" choice removed (`empty_label = None`) so the field always has a real default. `fulfillment_type` drops the Pickup option entirely when `shop.pickup_available` is `False`. `clean()` requires `delivery_zone` and `address` when `fulfillment_type` is Delivery.

### Views and URLs

- **`products/storefront_views.py`** — `cart_add`, `cart_view`, `cart_update`, `cart_remove`, `checkout` (all `@public_shop_required`). Every mutating endpoint is POST-only (GET returns 405) and follows the existing POST → `messages` → redirect (PRG) pattern already used across the merchant side of the codebase — there is no fetch/XHR anywhere in this change.
- **`orders/views.py::order_success_preview`** — new, `@public_shop_required`.
- **`config/urls.py`** — 6 new flat, unnamespaced `store/<slug:shop_slug>/...` routes (`cart_view`, `cart_add`, `cart_update`, `cart_remove`, `checkout`, `order_success`), matching the two existing storefront routes' pattern exactly.
- **`shops/decorators.py::public_shop_required`** — now stashes `request.public_shop = shop` on the success path, so the cart-badge context processor can reuse it without an extra query.
- **`shops/context_processors.py::storefront_cart`** (new) — exposes `cart_count` to every storefront template.

### Templates and styling

- **New:** `templates/storefront/cart.html`, `checkout.html`, `order_success.html`.
- **`templates/storefront/product_detail.html`** — the variant/quantity/Add to Cart controls are now wrapped in a real `<form>` that POSTs to `cart_add`, replacing the previous cosmetic-only JS behaviour (permanent button disable, no persistence).
- **`templates/components/product_card.html`** — the quick-add button is now a real link to the product detail page, since a catalog card never knows which specific variant to add.
- **`templates/components/navbar_public.html`** — a cart icon with a live item-count badge.
- **`templates/storefront/base_public.html`** — Django messages are bridged into the existing toast element via a data attribute, read by a new shared `static/storefront/js/toast.js`.
- **`static/storefront/css/storefront.css`** — styling for the new pages: colored icon badges per checkout section, a custom-built dropdown component (`static/storefront/js/custom-select.js`) replacing the native `<select>` appearance for delivery area/payment method/currency, entrance animations on cart/checkout content, and a checkmark-draw + pulsing-ring animation plus a count-up total on the order-success page. All animations respect `prefers-reduced-motion`.

## Security and data isolation

- `@public_shop_required` resolves `shop_slug` to a `Shop` and blocks access entirely when the shop has no active subscription.
- `cart.get_lines()` filters resolved variants by `product__shop_id=shop.pk`, so a variant id that doesn't belong to the current shop is excluded rather than leaking cross-shop data.
- `cart_add` scopes its variant lookup to the shop resolved from the URL, so a forged `variant_id` belonging to a different shop is rejected with a clean redirect + message rather than being added (covered by `CartViewTests.test_adding_variant_from_different_shop_is_rejected`).
- Every mutating endpoint is POST-only; CSRF protection applies to all forms.
- No stock or price validation happens in this cart/checkout layer by design — that enforcement is explicitly left to the real checkout service.

## Automated testing

- **`products/test_cart.py`** (new, 20 tests):
  - `CartStorageTests` (7) — accumulation on repeat add, two shops' carts staying isolated, `update_item(quantity=0)` removing a line, `get_lines` excluding and pruning a deleted/deactivated/wrong-shop variant, `get_totals` keeping USD/LBP separate.
  - `CartViewTests` (6) — a valid add showing up on the cart page, a cross-shop add being rejected, GET on `cart_add` returning 405, update/remove reflected on the next page load, the empty-cart state.
  - `CheckoutViewTests` (7) — only active zones/enabled payment methods listed, the Pickup option present/absent based on `shop.pickup_available`, an empty cart redirecting instead of rendering the form, a valid POST creating zero `Order`/`OrderItem` rows and leaving the cart untouched, a missing zone/address re-rendering the form with field errors.
- **`orders/tests.py`** (new, 4 tests): `OrderSuccessPreviewTests` — a direct visit shows the generic fallback order, the real checkout→success path shows the actual submitted name/items (not the fallback), and the preview banner text is present on both paths.

## Manual verification

- Seeded a shop (`demo-fashion`) with products, a delivery zone, and payment methods via `manage.py seed_demo_data` plus a one-off shell command for the zone/payment rows.
- Added items from both the product detail page and confirmed the navbar badge count updated on the next page load.
- Adjusted quantity and removed a line on the cart page.
- Walked through checkout with both Delivery and Pickup, confirmed the delivery-area/address fields hide correctly for Pickup.
- Confirmed via `curl`/Django shell that `Order.objects.count()` and `OrderItem.objects.count()` stayed at 0 after a valid checkout submission.
- Confirmed the order-success page reflects the real submitted name/items right after checkout, and falls back to the generic example on a direct/bookmarked visit.
- Confirmed the delivery-area/payment-method/currency dropdowns render with real options and no blank placeholder choice.

## Verification results

```powershell
python manage.py check
python manage.py test products.test_cart orders
python manage.py test
```

- Django's system check identified no issues.
- `products.test_cart` + `orders`: **24 tests passed** (20 + 4).
- Complete test suite: **323 tests passed**.

## Files changed

- `products/cart.py` (new)
- `products/test_cart.py` (new)
- `products/forms.py`
- `products/storefront_views.py`
- `orders/views.py`
- `orders/tests.py`
- `shops/decorators.py`
- `shops/context_processors.py`
- `config/settings.py`
- `config/urls.py`
- `templates/storefront/cart.html` (new)
- `templates/storefront/checkout.html` (new)
- `templates/storefront/order_success.html` (new)
- `templates/storefront/base_public.html`
- `templates/storefront/product_detail.html`
- `templates/components/navbar_public.html`
- `templates/components/product_card.html`
- `static/storefront/css/storefront.css`
- `static/storefront/js/toast.js` (new)
- `static/storefront/js/custom-select.js` (new)
- `static/storefront/js/catalog.js`
- `static/storefront/js/product-detail.js`

## Dependencies

- Depends on `ProductVariant` (products app), already in place.
- Uses `Order`, `OrderItem`, `Customer`, `DeliveryZone`, and `ShopPaymentMethod` models already on `develop`.
- Blocked on SCRUM-65 (Reem's `orders.services.create_order`) for wiring real order submission — checkout and order-success currently only build and render a preview, no order is ever persisted.

## Known limitations or follow-up work

- Checkout does not call a real order-creation service yet — it builds a preview payload only, pending SCRUM-65.
- The order-success page shows either the real submitted preview (popped from the session once) or a static generic fallback example; it does not yet query a real saved `Order`.
- No price/stock validation happens in the cart or checkout views — that belongs to the real checkout service once it merges.

## Final result

Guests can now add products to a real, session-backed cart from the product detail page, see a live item-count badge in the navbar, and manage quantities/removals on a dedicated cart page. They can walk through a fully-styled checkout form (contact details, delivery or pickup, payment method, currency) and reach an order-success page that reflects their real submission — all without any order actually being created yet, since the real order-creation service is still pending on a teammate's branch. The templates and views are built so that wiring real submission in later (once SCRUM-65 merges) requires no template changes, only swapping the preview-building logic for a real service call.
