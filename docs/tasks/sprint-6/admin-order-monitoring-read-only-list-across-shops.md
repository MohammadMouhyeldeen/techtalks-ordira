# Admin Order Monitoring — Read-Only Orders Across Shops

-**Owner:** Jinane
- Sprint: 6
- Ticket: SCRUM-92
- Branch: `feature/admin-order-monitoring`
- Target branch: `develop`
- Scope: Admin-only, read-only order monitoring across all shops

## Objective

Provide platform administrators with a centralized view of recent orders across Ordira shops. Administrators can inspect order information and filter results by shop and status without performing order-management actions.

## Scope

- Display the latest 100 orders across all shops, ordered newest first.
- Display shop name, order number, status, total with currency, and creation date.
- Provide shop and status filters using GET parameters.
- Include an Order Monitoring link on the admin dashboard.
- Restrict the page to platform administrators.
- Reject non-GET requests to keep the monitoring endpoint read-only.
- Handle orders whose product variants or delivery zones have been deleted without breaking the page.
- Display an empty state when no orders match the selected filters.

## Acceptance Criteria

- [x] An administrator can view orders belonging to multiple shops.
- [x] Orders are limited to the latest 100 matching records.
- [x] Administrators can filter orders by shop.
- [x] Administrators can filter orders by status.
- [x] Anonymous users are redirected to login.
- [x] Shop owners are redirected away from the admin-only page.
- [x] The page displays an empty state when there are no matching orders.
- [x] Deleted product variants do not break order monitoring, and saved order-item snapshots remain available.
- [x] Deleted delivery zones do not break order monitoring, and the saved zone-name snapshot remains available.
- [x] POST requests are rejected with HTTP 405, without changing order status.
- [x] The admin dashboard links to Order Monitoring.
- [x] No order status, cancellation, or payment actions are provided on the monitoring page.

## Implementation

- `accounts/views.py`: Admin-only order list, shop/status filtering, newest-first ordering, and the 100-order limit.
- `accounts/urls.py`: Named route `accounts:admin_orders`.
- `templates/accounts/admin_orders.html`: Read-only order table, filters, and empty state.
- `templates/accounts/admin_dashboard.html`: Link to the monitoring page.
- `accounts/test_admin_orders.py`: Focused automated tests for the monitoring feature.

## Verification

The following checks were run successfully:

| Check | Result |
|---|---|
| `python manage.py test accounts.test_admin_orders` | 11 tests passed |
| `python manage.py test` | 524 tests passed |
| `python manage.py check` | No issues identified |
| `git diff --check` | No whitespace errors reported |
