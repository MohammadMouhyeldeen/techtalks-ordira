# SCRUM-77 — Order Cancellation Service

**Owner:** Reem Saijary
**Sprint:** Sprint 5
**Date completed:** October 5, 2026
**Status:** Ready for review
**Related ticket:** SCRUM-77
**Branch:** `feature/SCRUM-77-order-cancellation`
**Target branch:** `develop`

## Task objective

The purpose of SCRUM-77 was to implement a safe Order cancellation service that restores the inventory deducted during checkout.

When an eligible Order is cancelled, Ordira must:

- Save the cancellation reason.
- Change the Order status to `CANCELLED`.
- Restore the quantities of its Order Items to inventory.
- Create a `StockMovement` audit record for every restored Product Variant.
- Record when the stock was restored.
- Prevent repeated cancellation requests from restoring stock more than once.

This service is also required by SCRUM-68, which handles merchant Order-status transitions.

## Why a dedicated service was used

Order cancellation affects several database records:

- The Order status
- The cancellation reason
- The stock quantity of each Product Variant
- The Order’s stock-restoration timestamp
- The inventory audit trail

Keeping this business logic inside `orders/services.py` allows views and future status-transition features to call one centralized and tested function.

The service is executed inside a database transaction so all cancellation operations either succeed together or fail together.

This prevents partial results such as changing an Order to cancelled without restoring its stock.

## Cancellation service

The following service was added to `orders/services.py`:

```python
cancel_order(order, reason)
```

The service receives:

- The Order that should be cancelled
- The reason for cancellation

It returns the cancelled Order after completing the operation.

## Order locking

The service retrieves the Order again using:

```python
Order.objects.select_for_update()
```

This applies a database row lock for the duration of the transaction.

The lock prevents two requests from cancelling the same Order simultaneously and both restoring its stock.

After the first request completes the cancellation, the second request reads the updated Order and detects that it is already cancelled.

## Cancellation eligibility

The service validates the current Order status before changing anything.

### Already-cancelled Orders

If the Order is already cancelled, the service returns it without restoring stock again.

This makes cancellation idempotent, meaning that repeating the same operation does not produce additional inventory changes.

The repeated request does not:

- Increase stock again
- Create duplicate cancellation movements
- Replace the original cancellation reason
- Replace the original stock-restoration timestamp

### Completed Orders

An Order with the `COMPLETED` status cannot be cancelled.

The service raises a validation error:

```text
Completed orders cannot be cancelled.
```

No Order data or inventory is changed when this validation fails.

## Restoring inventory

The service reads the Order Items connected to the Order.

For every Order Item that still references a Product Variant, it:

1. Locks the Product Variant.
2. Adds the ordered quantity back to `stock_quantity`.
3. Saves the updated stock quantity.
4. Creates a cancellation `StockMovement`.

For example, if checkout reduced a Variant’s stock from 10 to 8 by purchasing two units, cancelling the Order restores the stock from 8 to 10.

## Inventory audit trail

Every restored Product Variant receives a new `StockMovement` record with:

```python
reason = StockMovement.Reason.CANCELLATION
change_qty = order_item.quantity
```

The quantity change is positive because inventory is being returned.

The movement preserves a permanent record showing that the stock increase happened because an Order was cancelled.

Because the cancellation is performed by the system-level service, `created_by` is stored as `None`.

## Preventing duplicate restoration

The Order model already includes:

```python
stock_restored_at = models.DateTimeField(
    blank=True,
    null=True,
)
```

After inventory is restored successfully, the cancellation service records the current date and time in `stock_restored_at`.

The service checks both the Order status and this field to ensure that stock cannot be restored more than once.

This protects inventory even when:

- A user clicks the cancellation action repeatedly.
- The browser resubmits a request.
- Two cancellation requests arrive at nearly the same time.
- Another service calls cancellation for an already-cancelled Order.

## Historical Order Items

`OrderItem.variant` allows `NULL` values so historical Order information can remain available if its original Product Variant is later removed.

When cancelling an Order, the service skips an Order Item whose Variant no longer exists.

The Order can still be cancelled because its snapshot fields preserve:

- Product name
- Color
- Size
- Unit price
- Quantity
- Line total

No inventory movement is created for the missing Variant because there is no existing inventory record to update.

## Cancellation reason

A cancellation reason is required.

Whitespace-only values are rejected with a validation error. A successful reason is stored in:

```python
order.cancellation_reason
```

This allows the merchant and project team to understand why the Order was cancelled.

## Automated testing

A dedicated test module was created:

```text
orders/test_cancellation.py
```

The tests verify that:

- Cancelling an Order restores its stock.
- A cancellation `StockMovement` is created.
- The cancellation reason is saved.
- `stock_restored_at` is recorded.
- Repeating cancellation does not restore stock twice.
- Repeating cancellation does not create duplicate movements.
- Completed Orders cannot be cancelled.
- Missing Product Variants are skipped without an error.
- Blank cancellation reasons are rejected.
- Two concurrent cancellation requests restore stock only once.

## Concurrency testing

The concurrency test uses Django’s `TransactionTestCase`, separate database connections, and two worker threads.

Both threads attempt to cancel the same Order at approximately the same time.

The test confirms that the Order lock works correctly by verifying that:

- The Order becomes cancelled.
- Stock returns to its original quantity only once.
- Exactly one cancellation `StockMovement` exists.

## Verification results

The following checks were completed:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test orders.test_cancellation
python manage.py test orders
python manage.py test
git diff --check
```

Results:

- Django’s system check identified no issues.
- No model changes or new migrations were required.
- All 6 dedicated cancellation tests passed.
- All 26 Order application tests passed.
- The complete project test suite passed: 394 tests.
- No whitespace errors were found.

The Windows logging system displayed file-rotation warnings because `logs/app.log` was open in another process. These warnings did not affect the tests, which completed successfully.

## Files changed

- `orders/services.py`
- `orders/test_cancellation.py`
- `docs/tasks/sprint-5/SCRUM-77-order-cancellation.md`
- `docs/README.md`

## Dependencies

SCRUM-77 depends on the checkout workflow implemented in SCRUM-65 because cancellation restores inventory previously deducted during Order creation.

SCRUM-77 is also required by SCRUM-68. The status-transition workflow can call `cancel_order()` when moving an eligible Order to the cancelled status.

## Final result

Ordira now has a transactional and concurrency-safe Order cancellation service.

Eligible Orders can be cancelled with a recorded reason, their inventory is restored with a permanent audit trail, repeated cancellation requests cannot restore stock twice, completed Orders are protected, and historical Order Items with deleted Variants are handled safely.