# SCRUM-68 — Order Status Transitions and Merchant Controls

**Owner:** Jinane Al Ammar
**Sprint:** Sprint 5
**Date:** October 10, 2026
**Status:** Implementation complete — final full-suite validation pending
**Related ticket:** SCRUM-68
**Branch:** `feature/SCRUM-68-order-status-flow`
**Target branch:** `develop`
**Reviewer:** Mohammad
**Tester:** Farah
**Related tickets:** SCRUM-64, SCRUM-77

## Task objective

SCRUM-68 introduces the merchant-facing workflow for advancing an order through its supported statuses. It adds a centralized transition service and controls on the merchant order-detail page.

The supported forward workflow is:

`NEW` → `PREPARING` → `HANDED_TO_DELIVERY` → `COMPLETED`

Completed and Cancelled are terminal states. The implementation does not recreate cancellation or inventory-restoration logic, which belongs to SCRUM-77.

## Order status transition service

The `transition_order_status()` function in `orders/services.py` centralizes forward status transitions.

The service:

* Defines the permitted next status for each non-terminal status.
* Rejects skipped, backward, invalid, and terminal-state transitions with clear validation errors.
* Locks the order row during the transition using `select_for_update()`.
* Saves the new status through the service rather than directly in the merchant view.

Completed and Cancelled orders cannot be advanced through the normal transition workflow.

## Merchant order actions

The `merchant_order_action` view handles submitted merchant actions. The endpoint is registered as `orders:order-action`.

The endpoint:

* Requires authentication and POST requests.
* Uses the shop ownership check and retrieves the order within that shop.
* Calls `transition_order_status()` for forward status changes.
* Displays success or validation messages using Django messages.
* Redirects to the merchant order-detail page after processing the action.

The view does not assign the order's status directly.

## Order-detail controls

The merchant order-detail template displays the actions appropriate to the current status.

| Current status     | Available actions               |
| ------------------ | ------------------------------- |
| New Order          | Mark as Preparing; Cancel Order |
| Preparing          | Hand to Delivery; Cancel Order  |
| Handed to Delivery | Mark as Completed; Cancel Order |
| Completed          | No actions                      |
| Cancelled          | No actions                      |

The forms submit POST requests and include CSRF tokens. The cancellation form requires a reason.

## Cancellation delegation

Cancellation remains owned by SCRUM-77. The merchant action view calls the existing `cancel_order()` service and passes the submitted reason.

The SCRUM-68 view does not restore stock or duplicate cancellation-service logic. If the cancellation service rejects a request, such as an attempt to cancel a Completed order, its validation error is displayed to the merchant.

## Security and access control

The implementation enforces the following protections:

* Authentication is required for merchant actions.
* GET requests are rejected by the POST-only endpoint.
* CSRF protection is provided through Django's CSRF middleware and form tokens.
* Orders are retrieved within the selected owner-controlled shop; an order belonging to another shop returns 404.
* Status changes are performed through the transition service rather than by direct assignment in the view.

## Tests

The focused `CheckoutServiceTests` run passed with **32 tests**.

Coverage includes:

* Every permitted forward transition.
* Skipped and backward transitions.
* Invalid status values.
* Completed and Cancelled terminal states.
* Rejection of every invalid source-status/target-status combination.
* Successful merchant status updates.
* Invalid-transition messages.
* Cross-shop order access returning 404.
* GET requests rejected with HTTP 405.
* CSRF enforcement.
* Cancellation delegation to SCRUM-77.
* Display of rejected cancellation errors.
* Correct action visibility for each order status.

The full project test suite must be run again after the final test-coverage additions. Its result will be recorded before the task is submitted for review.
