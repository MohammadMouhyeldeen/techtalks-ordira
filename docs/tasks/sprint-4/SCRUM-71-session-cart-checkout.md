# SCRUM-71 — Session Cart + Real Guest Checkout

**Owner:** Hadi Assi<br>
**Sprint:** Sprint 4<br>
**Date completed:** October 6, 2026<br>
**Status:** Completed and merged<br>
**Related ticket:** SCRUM-71<br>
**Branch:** `feature/SCRUM-71-session-cart-checkout` (cart + checkout/order-success shells), `feature/SCRUM-71-real-order-integration` (real order submission)<br>
**Pull request:** https://github.com/MohammadMouhyeldeen/techtalks-ordira/pull/43 (merged), https://github.com/MohammadMouhyeldeen/techtalks-ordira/pull/51<br>
**Target branch:** `develop`

## Task objective

Build a real, fully-working guest checkout flow for the public storefront: a session-backed shopping cart, a checkout form, and real order submission. A guest can browse the catalog, add items to a cart, check out with their contact/fulfillment/payment details, and receive a real, persisted order with a shareable confirmation link — with stock deducted and a customer record created.

This landed in two PRs. The order-creation service (`orders.services.create_order`, SCRUM-65) was still on a teammate's unmerged branch when the cart/checkout UI work started, so PR #43 built the session cart (fully real, no blockers) plus checkout and order-success page **shells** — demoable end-to-end, but not yet creating real orders. Once SCRUM-65 merged, PR #51 wired checkout to the real service, replacing the shell behaviour with actual order creation.

## Why this task was needed

Sprint 4's goal is a guest checkout flow. Before this task, the storefront had a catalog and product detail page (SCRUM-46/SCRUM-52) but no way to actually collect items or place an order — "Add to Cart" buttons were cosmetic only (a local button-state change and a toast, with no real cart, no persistence, and no shared state between pages).

The two-PR split let the cart and UI work start on day one without waiting on SCRUM-65, while still giving the rest of the team (Mohammad's merchant order views, Jinan's status transitions, the tracking page) a real, working guest checkout to build against once the order service landed — rather than everyone blocking on one large PR.

## Requirements

- Session-backed cart: add/update/remove variant lines, quantity, subtotal.
- Checkout form and an order confirmation page.
- Real order submission via `orders.services.create_order`, once available — no order/stock/price validation logic duplicated here; that belongs to the checkout service.
- Guests should reach a real, working checkout even before the order service existed (via the shell), with zero template changes needed once it was wired up for real.

## Implementation

### Models and database

No model changes or migrations were required by this ticket's own work. Uses the already-migrated `Order`/`OrderItem`, plus `Customer`, `DeliveryZone`, and `ShopPaymentMethod`.

### Business logic

- **`products/cart.py`** — the session cart. Storage shape is `request.session["cart"] = {"<shop_id>": {"<variant_id>": quantity}}`, nested by shop. Functions: `add_item`, `update_item` (quantity ≤ 0 removes the line), `remove_item`, `get_lines`, `get_item_count`, `get_totals`, `get_raw_count`, `clear`.
  `get_lines` resolves variants fresh against the database on every call and silently prunes any session entry that no longer resolves (deleted/deactivated variant, wrong shop, or even a malformed key) — both from the result and from the session itself. `_cart`/`_bucket` are read-only (`.get()`, not `.setdefault()`): browsing the catalog, a product page, or an empty cart page never creates a session row or sets a cookie — only `add_item` ever creates the session structure. `add_item` also clamps the added quantity to the variant's current stock, and `update_item`/`remove_item` only ever modify a key that's already present, so a bad or unresolved `variant_id` can never plant an entry and poison the session.
- **`products/storefront_views.py::checkout`** — builds the item list from the real cart lines and calls `orders.services.create_order(shop=, customer_name=, customer_phone=, fulfillment_type=, selected_payment_method=, items=, currency=, delivery_zone=, address=)` directly. A `ValidationError` from the service (insufficient stock discovered at submission time, a disabled payment method, a cross-shop delivery zone, etc.) is caught and attached to the form as a non-field error, re-rendering checkout with the real message — no order is created in that case. On success, the cart is cleared (`cart.clear()`, not before) and the guest is redirected to the real order's confirmation page.
- **`orders/views.py::order_success`** — looks up a real, saved `Order` by `tracking_token` (a UUID field already on the model) scoped to the shop, and renders it. **Never looks up by primary key** — a sequential pk would let anyone enumerate other customers' orders and read their name/phone/address just by incrementing the URL.
- **`products/storefront_views.py::cart_add`/`cart_update`** additionally reject a variant with zero stock outright and clamp the requested quantity to the variant's current stock — both enforced server-side, since the UI's disabled state alone isn't a real guarantee.

### Forms and validation

- **`products/forms.py::CheckoutForm`** — a plain `forms.Form`, constructor takes `shop=` like `ProductForm`/`CategoryForm`. Fields: `customer_name`, `customer_phone`, `fulfillment_type` (Delivery/Pickup), `delivery_zone`, `address`, `selected_payment_method`, `currency`.
  `delivery_zone` and `selected_payment_method` querysets are scoped to the shop's active zones / enabled payment methods, with the blank "---------" choice removed (`empty_label = None`). `fulfillment_type` drops Pickup entirely when `shop.pickup_available` is `False`. `clean()` requires `delivery_zone` and `address` when `fulfillment_type` is Delivery. This form-level validation is a UX convenience; the authoritative validation is `create_order`'s own.

### Views and URLs

- **`products/storefront_views.py`** — `cart_add`, `cart_view`, `cart_update`, `cart_remove`, `checkout` (all `@public_shop_required`). Every mutating endpoint is POST-only (GET returns 405), parses `variant_id` via `int()` in a try/except so a malformed value redirects cleanly instead of raising, and follows the existing POST → `messages` → redirect (PRG) pattern used elsewhere in the codebase.
- **`orders/views.py::order_success`** — real confirmation page, `@public_shop_required`.
- **`config/urls.py`** — `store/<slug:shop_slug>/cart/...` routes as before; `order-success` now takes a `<uuid:tracking_token>` URL segment instead of relying on session state, so the confirmation link is real and shareable/bookmarkable.
- **`shops/decorators.py::public_shop_required`** — stashes `request.public_shop = shop` on the success path, so the cart-badge context processor can reuse it without an extra query.
- **`shops/context_processors.py::storefront_cart`** — exposes `cart_count` to every storefront template.

### Templates and styling

- **`templates/storefront/cart.html`, `checkout.html`, `order_success.html`** — the guest cart, checkout form, and order confirmation pages. The "this is a preview" banners that existed on `checkout.html`/`order_success.html` during the shell phase have been removed now that both pages are real.
- **`templates/storefront/product_detail.html`** — the variant/quantity/Add to Cart controls are wrapped in a real `<form>` that POSTs to `cart_add`.
- **`templates/components/product_card.html`** — the quick-add button is a real link to the product detail page (a catalog card never knows which specific variant to add).
- **`templates/components/navbar_public.html`** — a cart icon with a live item-count badge.
- **`templates/storefront/base_public.html`** — Django messages are bridged into the existing toast via a data attribute, read by `static/storefront/js/toast.js`.
- **`static/storefront/css/storefront.css`** — styling for the cart/checkout/order-success pages: colored icon badges per checkout section, a custom-built dropdown component (`static/storefront/js/custom-select.js`) replacing the native `<select>` appearance, entrance animations, and a checkmark-draw + pulsing-ring animation plus a count-up total on the order-success page — all respecting `prefers-reduced-motion`.

## Security and data isolation

- `@public_shop_required` on every route — blocked entirely for a shop with no active subscription.
- `cart.get_lines()` scopes resolved variants to the shop, so a variant belonging to a different shop never appears in the cart or can be added (`CartViewTests.test_adding_variant_from_different_shop_is_rejected`).
- `cart_add`/`cart_update` reject an out-of-stock variant and clamp quantity to current stock, enforced server-side rather than relying on the UI's disabled attribute.
- `variant_id` is parsed via `int()` with a try/except on every mutating cart endpoint; a malformed value redirects cleanly instead of raising a 500 or being written into the session as an unresolvable key.
- The session cart is read-only on every page that doesn't actually mutate it, so simply browsing never creates a session row or cookie for that visitor.
- **Order-success is looked up by `tracking_token` (an unguessable UUID), never by sequential pk** — prevents a stranger from enumerating other customers' orders and reading their name, phone, and address.
- The authoritative order-creation validation (stock, payment method, delivery zone ownership, variant-shop ownership, `FOR UPDATE` row locking) lives in `orders.services.create_order` (see `docs/tasks/sprint-4/SCRUM-65-order-checkout.md`) and is exercised end-to-end from this checkout flow; any `ValidationError` it raises is surfaced to the guest as a normal form error rather than a crash.

## Automated testing

- **`products/test_cart.py`** (36 tests): `CartStorageTests` (12), `CartViewTests` (13), `CheckoutViewTests` (8), `CartSessionHygieneTests` (3) — cart accumulation/isolation/pruning, stock clamping and out-of-stock rejection on add/update, malformed `variant_id` handled cleanly on add/update/remove with no session corruption, no session cookie created by read-only browsing, a valid checkout creating a real order and clearing the cart, and a real `ValidationError` (insufficient stock discovered at submission) re-rendering the form instead of creating an order.
- **`orders/tests.py::OrderSuccessViewTests`** (3 tests, this ticket): a real order's success page shows the actual submitted data, an unknown `tracking_token` 404s, and an order looked up under the wrong shop 404s.
- **`orders/tests.py::CheckoutServiceTests`** (16 tests, SCRUM-65 — see that ticket's own doc) exercises `create_order` directly and is what this checkout flow now calls into.
- `products.test_cart` + `orders` together: **55 tests passing.**
- Full suite: **371 tests passing.**

## Manual verification

- Live end-to-end walkthrough (catalog → product → cart → checkout → order-success) against the dev server: a real `Order` row is created with the correct snapshot data, stock is deducted by the ordered quantity, a `Customer` row is created from the submitted phone number, the cart is cleared after a successful submission, and the order-success page shows the real submitted data and still shows it correctly on reload (it's a real saved order now, not a one-time session pop).
- Confirmed an unknown or cross-shop `tracking_token` 404s cleanly rather than leaking another shop's order.
- Simulated a stock race condition (dropped a variant's stock to 0 after it was already in the cart, before submitting) and confirmed checkout re-renders with the real "Not enough stock is available for..." message instead of silently succeeding.
- Confirmed the "this is a preview" banners are gone from both the checkout and order-success pages.
- All manual testing used fresh, first-time phone numbers — phone-number normalization is a separate, not-yet-merged ticket, so reusing a number across tests wasn't a reliable way to represent "the same returning customer" yet.

## Verification results

```powershell
python manage.py check
python manage.py test products.test_cart orders
python manage.py test
```

- Django's system check identified no issues.
- `products.test_cart` + `orders`: **55 tests passed.**
- Complete test suite: **371 tests passed.**

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

- Depended on SCRUM-65 (`orders.services.create_order`) for real order creation — merged, and this ticket's checkout flow calls it directly.
- Uses the `Shop`, `ProductVariant`, `DeliveryZone`, `ShopPaymentMethod`, `Customer`, `Order`, and `OrderItem` models.

## Known limitations or follow-up work

- No known limitations remain in the cart/checkout/order-creation flow itself.
- `Customer.get_or_create` (inside `create_order`) matches on the phone number exactly as submitted, with no normalization — a separate, not-yet-merged ticket covers normalizing phone formats. Until that lands, the same person typing their number differently across orders will be treated as separate customers.

## Final result

Guests can complete a full, real guest checkout: browse the catalog, add items to a session cart, check out with contact/fulfillment/payment details, and receive a real, persisted order — with stock deducted, a customer record created, and a shareable confirmation link keyed by an unguessable tracking token rather than a sequential ID. Verified by 55 passing targeted tests, 371 passing in the full suite, and a full live walkthrough including a simulated stock-race-condition error path.
