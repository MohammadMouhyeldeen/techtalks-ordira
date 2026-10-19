# SCRUM-94 — Customer Outstanding Balance

**Owner:** Hadi Assi<br>
**Sprint:** Sprint 6<br>
**Date completed:** October 15, 2026<br>
**Status:** Awaiting review<br>
**Related ticket:** SCRUM-94 (Epic SCRUM-75)<br>
**Branch:** `feature/SCRUM-94-customer-outstanding-balance`<br>
**Pull request:** Add the pull-request link<br>
**Target branch:** `develop`

## Task objective

Show the merchant how much each customer still owes — the total of that customer's unpaid, non-cancelled orders. Partial payments are out of scope for the MVP, so this is a simple sum, not a running ledger of partial amounts.

## Implementation

### Business logic

- **`customers/services.py::outstanding_orders(customer)`** (new) — `customer.orders.exclude(status=CANCELLED).filter(payment__isnull=True)`. `Payment` is a `OneToOneField` on `Order` (`related_name="payment"`), and `payments/services.py::record_payment` only ever creates one as `status=PAID`, in full, and only once per order (it raises if a `Payment` already exists for that order) — so "has no recorded payment" and "is unpaid" are the same condition today, and a single `payment__isnull=True` filter is both correct and a single query, rather than looping through orders in Python checking each one's payment status.
- **`customers/services.py::outstanding_balances(orders)`** (new) — sums `order.total` per `order.currency` into a `{currency: Decimal}` dict, e.g. `{"USD": Decimal("45.00")}`. Never adds a USD amount to an LBP one — two separate dict entries when a customer has unpaid orders in both.
- **`customers/views.py::customer_list`** — after building the existing annotated customer queryset, sets `customer.outstanding_balances` on each row (a Python attribute, not a DB annotation — conditional multi-currency aggregation in raw SQL would be far less readable for what's a handful of rows per shop at this scale).
- **`customers/views.py::customer_detail`** — evaluates `outstanding_orders(customer)` once into a list, then derives both `outstanding_balances` (the totals) and `outstanding_order_ids` (a `set` of pks) from that same list — no second query.

### Templates and styling

- **`templates/customers/customer_list.html`** — new "Outstanding balance" column; one `<li>` per currency, or `0.00` when there's nothing outstanding.
- **`templates/customers/customer_detail.html`** — new "Outstanding balance" card above the orders table (same per-currency list, or "0.00 — nothing outstanding"), and each order row in the existing orders table now carries a small "Outstanding" badge when its id is in `outstanding_order_ids` — this is "lists which orders make it up": the existing full order history is reused rather than duplicated into a second table, with the relevant rows marked instead.
- **`static/customers/css/customers.css`** (new) — `.balance-list` and `.outstanding-badge` only; everything else keeps reusing `orders/css/orders.css` as already established in SCRUM-93.

## Security and data isolation

Both `outstanding_orders`/`outstanding_balances` operate on `customer.orders` — the `Customer` instance itself is already resolved through `_get_owner_shop` + `shop=shop`-scoped lookup (SCRUM-93), so there's no path for another shop's orders to enter the calculation.

## Automated testing

**`customers/tests.py::CustomerOutstandingBalanceTests`** (new, 9 tests):
- An unpaid order counts toward the balance.
- A paid order (via the real `payments.services.record_payment`) is excluded.
- A cancelled order is excluded.
- Two currencies are shown as two separate entries, never summed together.
- A customer with no orders at all returns an empty balance (shows as zero).
- Balances are scoped correctly across two different shops.
- The list page's new column renders the right total.
- The detail page shows both the balance and marks the contributing order with the "Outstanding" badge.

## Manual verification

Live click-through against the running dev server (seeded `active.owner@ordira.test`, shop pk 17):
- `/shops/17/customers/` — outstanding balance column shows real per-customer totals (e.g. `28.00 USD`, `378.00 USD`).
- `/shops/17/customers/3/` — "Outstanding balance: 378.00 USD", with exactly the two orders summing to that total (`93.00 USD` + `285.00 USD`) each carrying the "Outstanding" badge.

## Verification results

```powershell
python manage.py check
python manage.py test customers -v2
python manage.py test
```

- Django's system check identified no issues.
- `customers`: **27 tests passed.**
- Complete test suite: **515 tests passed.**

## Files changed

- `customers/services.py` (new)
- `customers/views.py`
- `customers/tests.py`
- `templates/customers/customer_list.html`
- `templates/customers/customer_detail.html`
- `static/customers/css/customers.css` (new)

## Dependencies

- Depends on SCRUM-93 (customers list and detail) — merged.

## Known limitations or follow-up work

- Partial payments are explicitly out of scope for the MVP (per the ticket) — `Payment.Status.PENDING` exists on the model but is never produced by the current `record_payment` service, so this ticket treats "has a payment row" and "is paid" as equivalent; if partial payments are ever introduced, `outstanding_orders` would need to check `payment.status` rather than just existence.

## Final result

A merchant can now see, per customer, exactly how much is still owed — broken out by currency — both as a column on the customer list and as a dedicated section on the customer detail page, with the specific contributing orders marked directly in that customer's existing order history.
