# SCRUM-95 — Low-Stock Notifications

**Owner:** Reem Saijary<br>
**Sprint:** Sprint 6<br>
**Date completed:** October 14, 2026<br>
**Status:** Awaiting review<br>
**Related ticket:** SCRUM-95<br>
**Branch:** `feature/SCRUM-95-low-stock-notifications`<br>
**Pull request:** Pending<br>
**Target branch:** `develop`

## Task objective

The purpose of this task was to notify a Shop Owner when a Product Variant’s stock crosses from above its configured low-stock threshold to at or below that threshold.

The notification appears in the merchant interface, and the navbar bell displays the number of unread notifications.

## Why this task was needed

Before this implementation, Ordira stored low-stock thresholds but did not actively alert merchants when inventory became low.

A Shop Owner could therefore miss an important stock change after an Order or manual inventory adjustment. This could lead to unavailable products remaining visible in the catalog or delayed restocking.

The feature provides a clear warning while preventing repeated notifications when stock remains below the threshold.

## Requirements

- Create a low-stock notification when stock crosses from above the threshold to at or below it.
- Support stock reductions caused by Order checkout.
- Support manual inventory adjustments.
- Do not create repeated notifications while stock remains low.
- Allow another notification after stock is restored above the threshold and later becomes low again.
- Roll back notifications when the related stock transaction fails.
- Display the unread count in the merchant navbar.
- Provide a recipient-scoped notification list.
- Display each notification’s message, date, and read status.
- Allow the current recipient to mark all their notifications as read.
- Prevent one user from seeing or modifying another user’s notifications.

## Implementation

### Models and database

The existing `Notification` model and its `LOW_STOCK` notification type were used.

No model changes or database migrations were required.

### Low-stock business logic

Created `notifications/services.py` with the `notify_low_stock_if_crossed()` service.

The service compares the Product Variant’s previous quantity with its current quantity.

A notification is created only when:

- The previous quantity was above `low_stock_threshold`.
- The current quantity is at or below `low_stock_threshold`.

The Notification belongs to the Variant’s Shop and is addressed to that Shop’s Owner.

Because the rule checks for a threshold crossing, additional reductions while stock remains low do not create duplicates. Restocking above the threshold resets the condition, allowing a later reduction to create another notification.

### Inventory integration

Updated `products/services.py` so manual stock adjustments record the previous stock quantity before saving the new value.

After the stock is saved, the low-stock service checks whether the threshold was crossed.

The notification is created inside the existing atomic stock-adjustment transaction. If a later operation fails, the stock update, Stock Movement, and Notification are all rolled back together.

### Checkout integration

Updated `orders/services.py` so successful checkout stock deductions also call the low-stock service.

The previous quantity is captured before each Product Variant is reduced.

This logic runs inside the existing atomic Order-creation transaction. A failed checkout therefore cannot leave behind stock changes or low-stock notifications.

### Notification count

Created `notifications/context_processors.py`.

The context processor counts unread Notifications where the authenticated user is the recipient and makes the count available as `unread_notifications`.

It returns zero for anonymous users.

The context processor was registered in `config/settings.py`.

### Views and URLs

Added authenticated notification views:

- `notifications:list`
- `notifications:mark-all-read`

The list view returns only Notifications belonging to the authenticated recipient.

The mark-all-read view:

- Accepts POST requests only.
- Updates only unread Notifications belonging to the current user.
- Redirects back to the notification list.

The notification URLs were included in `config/urls.py`.

### Templates and styling

Created:

- `templates/notifications/notification_list.html`
- `static/notifications/css/notifications.css`

The notification page displays:

- Notification type
- Message
- Creation date and time
- Read or unread status
- A “Mark all as read” action when unread notifications exist
- An empty state when no notifications exist

Unread notifications receive a distinct visual style.

Updated `templates/components/navbar.html` so the notification bell links to the notification list and displays the real unread count.

The page includes responsive styling for smaller screens.

## Security and data isolation

All notification views require authentication.

The notification list filters by:

```python
recipient=request.user
```

The mark-all-read operation uses the same recipient filter. This prevents a Shop Owner from reading or updating another user’s Notifications.

## Automated testing

Eleven dedicated notification tests verify:

- Crossing the threshold through a manual adjustment creates one low-stock Notification.
- Remaining below the threshold does not create duplicate Notifications.
- Restocking above the threshold and crossing it again creates another Notification.
- Stock remaining above the threshold creates no Notification.
- A failed stock-adjustment transaction rolls back the Notification and stock change.
- Checkout crossing the threshold creates a low-stock Notification.
- A failed checkout transaction leaves no low-stock Notification.
- The notification list requires authentication.
- The list displays only the authenticated recipient’s Notifications.
- Mark all as read updates only the authenticated recipient’s Notifications.
- The mark-all-read endpoint rejects GET requests.

## Verification results

The following checks were completed:

- `python manage.py test notifications`
- `python manage.py test products orders notifications`
- `python manage.py test`
- `python manage.py check`
- `python manage.py makemigrations --check --dry-run`
- `git diff --check`
- Conflict-marker search across the affected files

Results:

- All 11 dedicated notification tests passed.
- All 192 related Products, Orders, and Notifications tests passed.
- The complete project test suite passed: 490 tests.
- Django’s system check identified no issues.
- No model changes or missing migrations were detected.
- No whitespace errors or Git conflict markers were found.

## Manual verification

The feature was also verified through the merchant interface.

A Product Variant was reduced from a stock quantity of 5 to its low-stock threshold of 3.

The verification confirmed that:

- One LOW_STOCK Notification was created.
- The Notification belonged to the correct Shop and recipient.
- The navbar bell displayed the unread count.
- The notification list displayed the correct message and read status.
- Mark all as read changed the Notification to read.
- The navbar unread badge disappeared afterward.

## Files changed

- `config/settings.py`
- `config/urls.py`
- `docs/README.md`
- `docs/tasks/sprint-6/SCRUM-95-low-stock-notifications.md`
- `notifications/context_processors.py`
- `notifications/services.py`
- `notifications/tests.py`
- `notifications/urls.py`
- `notifications/views.py`
- `orders/services.py`
- `products/services.py`
- `static/notifications/css/notifications.css`
- `templates/components/navbar.html`
- `templates/notifications/notification_list.html`

## Dependencies

SCRUM-95 uses the existing Notification model and LOW_STOCK notification type.

It integrates with:

- The manual stock-adjustment service in `products/services.py`.
- The atomic Order checkout service in `orders/services.py`.
- The merchant navbar notification badge.

New-order notifications are outside the scope of this task.

## Final result

Ordira now notifies the correct Shop Owner when a Product Variant crosses into low stock.

The implementation supports checkout and manual inventory adjustments, prevents duplicate warnings while inventory remains low, allows a new warning after restocking, preserves transactional rollback behavior, and provides a recipient-scoped interface for viewing and marking Notifications as read.
