# SCRUM-65 — Atomic Order Checkout Service

**Owner:** Reem Saijary
**Sprint:** Sprint 4
**Date completed:** October 3, 2026
**Status:** Completed and merged
**Related ticket:** SCRUM-65
**Branch:** `feature/SCRUM-65-order-checkout`

## Task objective

The purpose of SCRUM-65 was to implement the core checkout service responsible for safely creating customer orders.

The service validates the checkout data, calculates prices and delivery fees, creates the Order and its OrderItems, deducts inventory, and records every stock deduction through the existing StockMovement audit trail.

All checkout operations are performed inside a single database transaction. This ensures that an order cannot be partially created.

## Checkout service

A dedicated checkout service was created in:

```text
orders/services.py
```

The main service function is:

```python
create_order(...)
```

Keeping checkout logic inside a service separates business rules from HTTP views and allows the same checkout process to be reused from different interfaces.

The service handles:

- Customer information
- Delivery or pickup selection
- Payment-method validation
- Product Variant validation
- Stock availability
- USD and LBP conversion
- Order total calculation
- Customer creation or reuse
- Order creation
- OrderItem creation
- Inventory deduction
- StockMovement audit records

## Atomic database transaction

The checkout service uses Django’s `transaction.atomic`.

This means all checkout operations succeed together or fail together.

For example, if one requested Product Variant does not have enough stock:

- No Order is created.
- No OrderItems are created.
- No Customer is created.
- No stock quantity is changed.
- No StockMovement is created.

This prevents incomplete orders and inconsistent inventory records.

## Checkout validation

Before creating an Order, the service validates the submitted information.

### Customer validation

The customer’s name and phone number are required.

Blank values are rejected before any database records are created.

### Currency validation

The requested order currency must be one of the supported currencies:

- USD
- LBP

Unsupported currencies are rejected.

### Fulfillment validation

The fulfillment type must be either:

- Delivery
- Pickup

For delivery orders:

- A Delivery Zone is required.
- The Delivery Zone must belong to the selected Shop.
- The Delivery Zone must be active.
- A delivery address is required.

For pickup orders:

- Pickup must be enabled for the Shop.
- A Delivery Zone cannot be supplied.
- The delivery address is cleared.
- The delivery fee is zero.

### Payment-method validation

The selected ShopPaymentMethod must:

- Belong to the selected Shop.
- Be enabled.

A disabled payment method or a method belonging to another Shop is rejected.

SCRUM-65 validates and saves the selected payment method on the Order. Creating and managing the separate Payment record remains part of the payment workflow.

### Order-item validation

An Order must contain at least one item.

Every submitted item must contain:

- A Product Variant identifier
- A positive integer quantity

The service rejects:

- Missing variants
- Zero quantities
- Negative quantities
- Boolean quantities
- Invalid or non-integer quantities
- Variants that do not exist
- Variants belonging to another Shop
- Archived Products
- Archived Product Variants
- Quantities greater than the available stock

If the same Product Variant appears more than once in the submitted items, the quantities are combined into one OrderItem.

## Concurrency-safe inventory locking

The service locks the selected Product Variant rows using:

```python
select_for_update(of=("self",))
```

The variants are also ordered by their primary key before being locked.

This provides deterministic lock ordering and reduces the risk of database deadlocks when multiple customers attempt to purchase overlapping variants at the same time.

Only the ProductVariant rows are locked. The related Product rows are loaded for validation without being unnecessarily locked.

## Stock protection

After locking each Product Variant, the service checks the current stock quantity again.

This check happens inside the transaction, preventing two simultaneous checkout operations from using the same outdated stock value.

If the requested quantity is unavailable, checkout is rejected without modifying the database.

Stock quantities are never allowed to become negative.

## Currency conversion

Ordira supports orders in USD and LBP.

The checkout service uses the Shop’s:

```python
exchange_rate_lbp_per_usd
```

Prices are converted when a Product Variant’s currency differs from the selected Order currency.

The supported conversions are:

- USD to LBP: amount multiplied by the exchange rate
- LBP to USD: amount divided by the exchange rate
- Same currency: no conversion required

Money values are rounded to two decimal places using `ROUND_HALF_UP`.

The exchange rate used during checkout is stored in:

```python
fx_rate_snapshot
```

This preserves the original calculation even if the Shop changes its exchange rate later.

## Order totals

For every OrderItem, the service calculates:

```text
line total = converted unit price × quantity
```

The Order’s item total is the sum of all line totals.

For delivery orders:

```text
final total = items total + delivery fee
```

For pickup orders:

```text
final total = items total
delivery fee = 0
```

Delivery fees are treated as USD configuration values and converted when the Order currency is LBP.

## Customer creation and reuse

The service finds an existing Customer using:

- Shop
- Phone number

If no matching Customer exists, a new Customer record is created using the submitted name and phone number.

Customers remain isolated by Shop. The same phone number can belong to separate Customer records in different Shops.

## Order creation

Every successful checkout creates an Order containing:

- Shop
- Customer
- Selected payment method
- Delivery Zone when applicable
- Unique order number
- Unique tracking token
- Fulfillment type
- Customer name snapshot
- Customer phone snapshot
- Delivery-zone name snapshot
- Delivery-fee snapshot
- Address snapshot
- Items total
- Final total
- Order currency
- Exchange-rate snapshot

New Orders use the model’s default status:

```text
NEW
```

Order numbers use an `ORD-` prefix followed by securely generated random characters.

The tracking token is generated automatically using UUID values and can later be used for public order tracking.

## OrderItem snapshots

Each requested Product Variant creates one OrderItem containing:

- Product name snapshot
- Color snapshot
- Size snapshot
- Converted unit-price snapshot
- Quantity
- Line total

Snapshots preserve historical order information.

For example, if a Shop Owner changes a Product’s name or price after checkout, the existing Order continues showing the values that were used when it was created.

## Preserving historical OrderItems

The `OrderItem.variant` relationship was changed to allow null values and use:

```python
on_delete=models.SET_NULL
```

A migration was created:

```text
orders/migrations/0002_alter_orderitem_variant.py
```

This allows a Product Variant to be deleted later without deleting the historical OrderItem.

The OrderItem’s product name, size, color, price, quantity, and line total remain available through its snapshot fields.

## Inventory audit trail

After creating each OrderItem, the service deducts the purchased quantity from its Product Variant.

It also creates a StockMovement with:

```text
change_qty = negative purchased quantity
reason = SALE
created_by = None
```

`created_by` is null because checkout is performed by a guest customer rather than an authenticated Shop Owner.

This ensures that every checkout-related stock reduction has a corresponding inventory audit record.

## Automated testing

Sixteen tests verify the checkout service.

The tests cover:

- Order creation
- OrderItem creation
- Customer creation
- Snapshot values
- Unique order numbers
- Unique tracking tokens
- USD order totals
- LBP currency conversion
- Delivery-fee conversion
- Pickup orders with zero delivery fees
- Stock deduction
- StockMovement creation
- Transaction rollback when stock is insufficient
- Duplicate Variant entries being combined
- Invalid, zero, and negative quantities
- Cross-Shop Product Variant rejection
- Inactive Product rejection
- Inactive Product Variant rejection
- Disabled payment-method rejection
- Cross-Shop Delivery Zone rejection
- Pickup orders rejecting Delivery Zones
- Database queries using `FOR UPDATE`

## Review changes

The following improvements were made after code review:

- Added deterministic Product Variant ordering before locking.
- Limited `select_for_update` to ProductVariant rows.
- Added coverage for unique tracking tokens.
- Added inactive Product and Variant tests.
- Added cross-Shop Delivery Zone validation coverage.
- Added pickup-with-zone rejection coverage.
- Added zero and negative quantity coverage.
- Added a database-query assertion confirming that `FOR UPDATE` is used.
- Fixed the formatting of the `OrderItem.variant` model field.
- Removed an unrelated sidebar fix from the SCRUM-65 branch to keep the pull request focused.

## Verification results

The following checks were completed:

```powershell
python manage.py test orders
python manage.py check
python manage.py makemigrations --check --dry-run
git diff --check
```

Results:

- All 16 Order tests passed.
- Django’s system check identified no issues.
- No missing migrations were detected.
- No whitespace errors were found.
- The review changes were pushed successfully.
- The pull request was reviewed and merged into `develop`.

During project-wide testing, unrelated sidebar URL errors already present in the shared `develop` code were identified and reported separately. They were not included in SCRUM-65 to keep the checkout pull request within its assigned scope.

## Main files changed

- `orders/models.py`
- `orders/services.py`
- `orders/tests.py`
- `orders/migrations/0002_alter_orderitem_variant.py`

## Final result

Ordira now has a validated, transactional, and concurrency-aware checkout service.

A successful checkout creates an Order and its snapshot-based OrderItems, calculates USD or LBP totals, deducts inventory, and records StockMovement audit entries.

Invalid checkout attempts are rejected before they can leave partial data, and database row locking protects inventory when multiple checkout operations occur concurrently.