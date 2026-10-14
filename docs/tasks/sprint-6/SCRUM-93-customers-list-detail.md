# SCRUM-93 — Customers List and Detail With Order History

**Owner:** Hadi Assi<br>
**Sprint:** Sprint 6<br>
**Date completed:** October 14, 2026<br>
**Status:** Awaiting review<br>
**Related ticket:** SCRUM-93 (Epic SCRUM-74)<br>
**Branch:** `feature/SCRUM-93-customers-list-detail`<br>
**Pull request:** Add the pull-request link<br>
**Target branch:** `develop`

## Task objective

Let a merchant see their customers, and for each one, the orders that customer placed — scoped to their own shop. First part of the customer ledger (the outstanding-balance ticket, SCRUM-94, builds on this).

## Implementation

### Business logic

- **`customers/views.py::_get_owner_shop`** (new, private) — `get_object_or_404(Shop, pk=shop_pk, owner=request.user)`. Same four-line pattern already duplicated independently in `shops/views.py`, `products/views.py`, and `orders/views.py` — followed that existing per-app convention rather than importing one of those instead, since nothing in this codebase currently does.
- **`customers/views.py::customer_list`** — `Customer.objects.filter(shop=shop)` annotated with `order_count=Count("orders")` and `last_order_at=Max("orders__created_at")` (`Order.customer`'s `related_name` is `orders`), ordered by `F("last_order_at").desc(nulls_last=True)` then `full_name` — newest activity first, with no-orders customers (not currently reachable, since `create_order` always `get_or_create`s the `Customer` at order time) falling to the end instead of erroring.
- **`customers/views.py::customer_detail`** — `get_object_or_404(Customer, pk=customer_pk, shop=shop)`, so a customer belonging to a different shop 404s even if the shop_pk itself is valid and owned by the requester. Orders via `customer.orders.order_by("-created_at")`.

### Forms and validation

Not applicable — no form on either page.

### Views and URLs

- **`customers/urls.py`** (new) — `app_name = "customers"`, routes `shops/<int:shop_pk>/customers/` (`customers:list`) and `shops/<int:shop_pk>/customers/<int:customer_pk>/` (`customers:detail`), matching the exact literal paths and URL names the ticket (and SCRUM-98's sidebar wiring) specify.
- **`config/urls.py`** — `path("", include("customers.urls"))`, no prefix, so the app's own `shops/...` patterns produce exactly that literal path rather than a doubled segment.

### Templates and styling

- **`templates/customers/customer_list.html`** / **`customer_detail.html`** (new) — both extend `base.html` and reuse the existing `orders/css/orders.css` classes (`.orders-page`, `.orders-header`, `.orders-table*`, `.order-link`, `.order-status*`, `.order-back-link`, `.order-detail-header`, `.order-card`, `.orders-empty`) rather than introducing a parallel stylesheet for what is visually the same merchant list/detail chrome already established by `orders/order_list.html` and `order_detail.html` — no new CSS file needed.
- Each order row on the detail page links to the existing `orders:order-detail` page — nothing new there, reused as-is.
- **Did not touch `templates/components/sidebar.html`** — per the ticket, that's SCRUM-98's job, which only needs the `customers:list`/`customers:detail` names to exist, which they now do.

## Security and data isolation

- `_get_owner_shop` already 404s if the requesting user doesn't own `shop_pk`, before either view does anything else.
- `customer_detail`'s `shop=shop` filter means a customer from a different shop 404s even if `customer_pk` is a real, valid id — there's no path from a valid shop to another shop's customer data.
- Both views are `@login_required`; an anonymous request redirects to `accounts:login` before reaching either.

## Automated testing

**`customers/tests.py::CustomerViewTests`** (new, 9 tests):
- Anonymous request redirects to login.
- List shows only the requesting shop's customers.
- Empty state renders when the shop has no customers.
- List orders by newest order activity first.
- Order count and last-order date are correct on the list.
- Detail shows that customer's orders, newest first.
- Detail page links to the real `orders:order-detail` URL for each order.
- A customer belonging to another shop 404s on the detail page.
- Viewing another owner's shop's customer list 404s.

## Manual verification

Live click-through against the running dev server (logged in as the seeded `active.owner@ordira.test`, shop pk 17):
- `/shops/17/customers/` — 200, lists all 6 real customers under that shop (including today's SCRUM-89 test orders).
- `/shops/17/customers/3/` — 200, shows "hadi" and both of that customer's real orders with working links to their order-detail pages.
- Anonymous request to the list page — 302 to login.
- A nonexistent customer id under the shop's own pk — 404.

## Verification results

```powershell
python manage.py check
python manage.py test customers -v2
python manage.py test
```

- Django's system check identified no issues.
- `customers`: **19 tests passed.**
- Complete test suite: **488 tests passed.**

## Files changed

- `customers/views.py`
- `customers/urls.py` (new)
- `customers/tests.py`
- `config/urls.py`
- `templates/customers/customer_list.html` (new)
- `templates/customers/customer_detail.html` (new)

## Dependencies

- Depends on nothing — works independently of SCRUM-66 (phone normalization), per the ticket.
- SCRUM-94 (customer outstanding balance) and SCRUM-98 (sidebar wiring, Farah) both build on the URL names introduced here.

## Known limitations or follow-up work

- No sidebar entry yet — intentional, SCRUM-98 adds it.
- No pagination on either page — not required by the ticket; worth revisiting if a shop's customer/order volume grows.

## Final result

A merchant can now see every customer who has ordered from their shop (name, phone, order count, last-activity date, newest first), and drill into any one of them to see their full order history with working links back into the existing order-detail page — all strictly scoped to the merchant's own shop.
