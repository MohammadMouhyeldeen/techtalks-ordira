# SCRUM-49 — Inventory Stock Adjustment and Audit Trail

**Owner:** Reem Saijary<br>
**Sprint:** Sprint 3<br>
**Date:** September 28, 2026<br>
**Status:** Completed and merged<br>
**Related ticket:** SCRUM-49<br>
**Branch:** `feature/SCRUM-49-inventory`<br>
**Target branch:** `develop`

## Task objective

The purpose of SCRUM-49 was to replace direct, unaudited stock editing with a safer inventory-management workflow.

A Shop Owner can increase or decrease a Product Variant’s stock by entering:

- The quantity change
- The reason for the adjustment

Every successful adjustment creates a permanent `StockMovement` record. This provides an audit trail showing:

- When the stock changed
- How much it changed
- Why it changed
- Who performed the adjustment

## Why this feature was needed

Previously, `stock_quantity` could be edited directly through the Product Variant form.

Direct editing did not explain:

- Who changed the stock
- When the change occurred
- Why the stock changed
- How much was added or removed

The new workflow ensures that every manual stock change is recorded and traceable.

For example, if a Product Variant has a stock quantity of 10 and the owner records an adjustment of `-2` because two items were damaged:

- The new stock quantity becomes 8.
- A `StockMovement` record is created with `change_qty=-2`.
- The movement reason is saved as `DAMAGE`.
- The logged-in owner is saved as `created_by`.
- The date and time are saved automatically.

## Product Variant active status

An `is_active` field was added to `ProductVariant`:

```python
is_active = models.BooleanField(default=True)
```

A database migration was created to add this field to existing Product Variant records:

```text
products/migrations/0003_productvariant_is_active.py
```

This field supports soft deletion. A Product Variant that has inventory history can be archived instead of being permanently removed.

## Safe variant deletion and archiving

The previous deletion view always called:

```python
variant.delete()
```

However, `StockMovement.variant` uses `on_delete=models.PROTECT`.

Django therefore prevents the deletion of a Product Variant that has Stock Movement history. Without handling this situation, attempting to delete the Variant would raise a `ProtectedError` and could produce a server error.

The deletion workflow was updated so that:

- A Variant without Stock Movement records can be permanently deleted.
- A Variant with Stock Movement history is archived using `is_active=False`.
- `ProtectedError` is handled as a defensive fallback.
- Archived Variants are excluded from active Product and inventory pages.

This preserves inventory history and prevents an unhandled deletion error.

## Stock-adjustment service

A service layer was created in:

```text
products/services.py
```

The `adjust_variant_stock` service keeps inventory business logic separate from request-handling code.

The service:

1. Locks and retrieves the selected Product Variant.
2. Confirms that the Variant is active.
3. Rejects a zero adjustment.
4. Validates the Stock Movement reason.
5. Calculates the new stock quantity.
6. Rejects the adjustment if it would produce negative stock.
7. Updates `stock_quantity`.
8. Creates the corresponding `StockMovement` record.
9. Returns the newly created movement.

The operation runs inside a database transaction:

```python
@transaction.atomic
```

The Variant is retrieved using `select_for_update()` to prevent concurrent operations from changing the same stock quantity at the same time.

The transaction ensures that the quantity update and Stock Movement creation either succeed together or fail together.

This prevents situations where:

- Stock changes without an audit record.
- An audit record is created without changing stock.
- Concurrent adjustments overwrite one another incorrectly.

## Stock-adjustment form

A `StockAdjustmentForm` was added to validate manual inventory changes.

The form accepts:

- `change_qty`
- `reason`

Positive quantities increase stock, while negative quantities decrease it.

Examples:

- `5` adds five units.
- `-2` removes two units.

The form rejects invalid operations and displays a clear validation error when an adjustment would make the stock quantity negative.

Direct editing of `stock_quantity` was removed from the regular Product Variant form. Shop Owners must now use the audited stock-adjustment workflow.

## Inventory views and URLs

Owner-scoped views and routes were added for:

- Adjusting a Product Variant’s stock
- Viewing a Product Variant’s Stock Movement history

The views verify that:

- The user is authenticated.
- The Shop belongs to the authenticated owner.
- The Product belongs to that Shop.
- The Product Variant belongs to that Product.
- The Product Variant is active.

Cross-shop access and access to archived Variants return a `404 Not Found` response.

## Stock history

A Stock Movement history page was added for every active Product Variant.

The page displays:

- Adjustment date and time
- Quantity change
- Adjustment reason
- User who recorded the adjustment

Movements are displayed newest first.

This allows the Shop Owner to understand how the current stock quantity was reached.

## Low-stock detection

Low-stock detection was added to `ProductVariant`:

```python
@property
def is_low_stock(self):
    return self.stock_quantity <= self.low_stock_threshold
```

A Variant is considered low in stock when:

```text
stock_quantity <= low_stock_threshold
```

Examples:

- Stock `2`, threshold `3` → Low stock
- Stock `3`, threshold `3` → Low stock
- Stock `4`, threshold `3` → Not low stock

The Product details page displays a visual warning when a Variant reaches or falls below its configured threshold.

## Active-variant filtering

Product and Variant queries were updated to return only active Variants.

This prevents archived Variants from:

- Appearing in active Variant tables
- Being opened through the Variant details page
- Being edited
- Receiving stock adjustments
- Displaying stock history through normal owner routes

The archived records remain in the database so their historical Stock Movements are preserved.

## Templates and styling

Templates were created or updated for:

- Product details
- Product creation and editing
- Variant creation and editing
- Variant details
- Stock adjustments
- Stock Movement history

A dedicated Product stylesheet was added:

```text
static/products/css/products.css
```

The interface includes:

- Styled forms
- Validation messages
- Responsive inventory tables
- Stock and low-stock badges
- Styled action buttons
- Hover and focus effects
- Empty-state messages
- Responsive layouts consistent with the Ordira theme

## Automated testing

Tests were added for:

- Successful stock increases
- Successful stock decreases
- Stock Movement record creation
- Negative-stock rejection
- Zero-quantity rejection
- Invalid-reason rejection
- Archived Variant rejection
- Form validation
- Stock history ordering
- Owner and cross-shop isolation
- Variants with movement history being archived
- Variants without movement history being deleted
- Low-stock threshold behavior
- POST-only protection for inventory-changing operations

## Verification results

The following checks were completed:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test products
python manage.py test
git diff --check
```

Final verification after integrating the latest `develop` branch produced these results:

- Django’s system check identified no issues.
- No missing migrations were detected.
- All 74 Product application tests passed.
- The complete suite of 248 tests passed.
- No whitespace errors were found.
- The merge conflict in `products/views.py` was resolved.
- The feature branch was synchronized with `develop`.
- The pull request was reviewed and merged into `develop`.

## Main files changed

- `products/models.py`
- `products/forms.py`
- `products/services.py`
- `products/views.py`
- `products/urls.py`
- `products/tests.py`
- `products/migrations/0003_productvariant_is_active.py`
- `static/products/css/products.css`
- `templates/products/product_detail.html`
- `templates/products/product_form.html`
- `templates/products/variant_detail.html`
- `templates/products/variant_form.html`
- `templates/products/stock_adjustment_form.html`
- `templates/products/stock_movement_history.html`

## Final result

Ordira now has an owner-scoped and auditable inventory workflow.

Stock quantities can no longer be silently overwritten through the standard Product Variant form. Every manual adjustment is validated and recorded as a `StockMovement`.

The completed workflow:

- Prevents negative stock.
- Records who performed each adjustment.
- Records why and when stock changed.
- Identifies low-stock Variants.
- Protects inventory history.
- Safely archives Variants that have historical movements.
- Blocks cross-shop and archived-Variant access.

This provides a reliable inventory foundation for the Order and checkout workflows implemented in later tasks.