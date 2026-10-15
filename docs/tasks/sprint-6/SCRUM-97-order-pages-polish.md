# SCRUM-97 — Order Pages Polish

**Assignee:** Farah  
**Task:** Polish the merchant order pages  
**Scope:** Templates, CSS, and tests only. No changes to order logic.

## Objective

Improve the presentation and usability of the merchant order detail and storefront order tracking pages.

## Changes

### 1. Order Detail Page
- Improve the appearance and layout of order action buttons, including status advancement and cancellation.
- Improve the presentation of the cancellation reason.
- Maintain the existing order workflow and business logic.

### 2. Storefront Order Tracking
- Polish the order tracking page layout and visual consistency.
- Improve readability and the presentation of order information.

### 3. Orders CSS
- Update `static/orders/css/orders.css` to improve styling and consistency across the order pages.
- Keep the existing design conventions of Ordira.

### 4. Tests
- Update `orders/tests.py` to verify the relevant order page behavior and presentation requirements.

## Files Modified
- `templates/orders/order_detail.html`
- `templates/storefront/order_tracking.html`
- `static/orders/css/orders.css`
- `orders/tests.py`
- `docs/tasks/sprint-6/SCRUM-97-order-pages-polish.md`

## Scope Restrictions
No changes to order processing, status transition logic, or other business logic.

## Verification
Run the relevant order tests and review both pages to ensure the changes meet the acceptance criteria.
