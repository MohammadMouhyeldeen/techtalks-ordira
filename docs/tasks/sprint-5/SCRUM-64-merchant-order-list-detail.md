# SCRUM-64 â€” Merchant Order List and Detail

**Owner:** Reem Saijary
**Sprint:** Sprint 5
**Date completed:** October 7, 2026
**Status:** Ready for review
**Related ticket:** SCRUM-64
**Branch:** `feature/SCRUM-64-merchant-order-list-detail`
**Target branch:** `develop`

## Task objective

The purpose of SCRUM-64 was to provide Shop Owners with owner-facing pages for viewing and managing the Orders placed through their Shops.

A Shop Owner can now:

- Open an Order list from the merchant sidebar.
- View Orders belonging to their own Shop.
- Filter Orders by status.
- Open the details of a specific Order.
- Review customer, fulfillment, payment, item, and total information.
- See cancellation information when an Order has been cancelled.

The implementation follows Ordiraâ€™s Shop ownership boundary, preventing one Shop Owner from accessing another Shopâ€™s Orders.

## Merchant Order list

A merchant Order list view was added for each Shop.

The page displays the Shopâ€™s Orders with important summary information, including:

- Order number
- Customer name
- Fulfillment type
- Order total and currency
- Current status
- Creation date and time
- Link to view the complete Order details

Orders use the modelâ€™s default newest-first ordering, allowing the merchant to see recent Orders first.

An empty state is displayed when the Shop has no Orders matching the current selection.

## Order status filtering

The Order list supports filtering through a `status` query parameter.

The available filter choices are based on the existing Order statuses:

- New Order
- Preparing
- Handed to Delivery
- Completed
- Cancelled

When the merchant selects a status, only Orders with that status are displayed.

The selected filter remains visible in the form after the page reloads.

## Merchant Order detail

A merchant Order detail page was created to display the full saved information for one Order.

The page includes:

- Order number
- Current status
- Order creation date
- Customer name
- Customer phone number
- Fulfillment type
- Delivery zone
- Delivery address
- Selected payment method
- Purchased items
- Product name snapshot
- Color and size snapshots
- Unit price
- Quantity
- Line total
- Items subtotal
- Delivery fee
- Final Order total
- Cancellation reason when applicable

The page uses the Order and OrderItem snapshot fields so historical Orders continue displaying the values recorded during checkout, even if Product information changes later.

## Owner-scoped access

Both merchant Order views require authentication.

Before showing any Order data, the application verifies that the selected Shop belongs to the logged-in user.

The access path is:

**Authenticated User â†’ Owned Shop â†’ Order belonging to that Shop**

A Shop Owner cannot access another Shopâ€™s Order list or Order details by changing identifiers in the URL.

Unauthorized or cross-Shop access returns a `404 Not Found` response, preventing information about another Shopâ€™s Orders from being exposed.

## Views and routing

Merchant Order views were added to `orders/views.py`.

The following named routes were introduced through `orders/urls.py`:

- `orders:order-list`
- `orders:order-detail`

The Orders URL configuration was included in the projectâ€™s main URL configuration.

Named routes allow templates and shared components to generate Order links without using hard-coded URLs.

## Sidebar integration

The Orders entry in the merchant sidebar previously appeared as a disabled â€œComing soonâ€ item.

It was connected to the real merchant Order list using the named Order-list route and the current Shop identifier.

The Shop Owner can now open the Orders area directly from the shared dashboard sidebar.

## Templates and styling

Created owner-facing templates for:

- Merchant Order list
- Merchant Order detail

A dedicated stylesheet was added for the Orders interface.

The styling follows the existing Ordira Product-management interface and includes:

- Page headings and descriptions
- Responsive Order tables
- Status badges with different colors
- Filter controls
- Information cards
- Order-item tables
- Order-total summaries
- Empty-state messages
- Link hover and focus effects
- Responsive behavior for smaller screens

## Integration with the checkout workflow

SCRUM-64 builds on the Order records created through SCRUM-65.

The merchant pages read the saved Order and OrderItem data produced by the checkout service. They do not create Orders or modify inventory.

The Order detail page provides the location where later merchant actions can be added, including:

- Order status transitions
- Order cancellation
- Payment recording

SCRUM-78 will build on this detail page by adding the payment-recording workflow.

## Automated testing

A dedicated test module was created for the merchant Order views.

The tests verify:

- Authentication is required.
- A Shop Owner can access their own Order list.
- Orders from another Shop are not displayed.
- Order status filtering works.
- Order details display the saved Order information.
- Order items and snapshot values are displayed.
- A Shop Owner cannot access another Shopâ€™s Order detail.
- Unknown Orders return `404`.
- The sidebar links to the merchant Order list.

## Rebase and conflict resolution

Before final verification, the branch was rebased onto the latest `origin/develop`.

A conflict occurred in the import section of `orders/views.py` because the latest `develop` branch had replaced the old Order-success preview with the real tracking-token-based Order-success implementation.

The conflict was resolved by preserving:

- The latest real Order-success implementation from `develop`.
- The authentication import and merchant Order views from SCRUM-64.

The rebase then completed successfully.

## Verification results

The following commands were completed:

```powershell
python manage.py test orders.test_merchant_orders
python manage.py test orders
python manage.py test
python manage.py check
python manage.py makemigrations --check --dry-run
```

Results:

- All 9 dedicated merchant Order tests passed.
- All 34 Orders application tests passed.
- The complete project test suite passed: 403 tests.
- Djangoâ€™s system check identified no issues.
- No missing model migrations were detected.
- The branch was successfully rebased onto the latest `develop`.

## Main files changed

- `config/urls.py`
- `orders/views.py`
- `orders/urls.py`
- `orders/test_merchant_orders.py`
- `templates/components/sidebar.html`
- `templates/orders/order_list.html`
- `templates/orders/order_detail.html`
- `static/orders/css/orders.css`
- `docs/tasks/sprint-5/SCRUM-64-merchant-order-list-detail.md`
- `docs/README.md`

## Dependencies

SCRUM-64 depends on SCRUM-65 because the merchant interface displays Orders and Order Items created by the checkout workflow.

SCRUM-78 depends on SCRUM-64 because payment recording will be added to the merchant Order detail page.

## Final result

Ordira now provides Shop Owners with an owner-scoped Order-management interface.

Merchants can open their Order list from the sidebar, filter Orders by status, and review complete Order details. Cross-Shop access is blocked, historical checkout snapshots are preserved, and the interface is ready for the upcoming status-transition, cancellation, and payment-recording workflows.
