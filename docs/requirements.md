# Ordira Requirements

This document defines the functional and business requirements for the Ordira MVP.

Ordira is a Django-based platform designed primarily for small online shops in Lebanon that sell through Instagram and WhatsApp. It provides a public storefront for customers and a management dashboard for Shop Owners.

## 1. System actors

### Platform Admin

The Platform Admin manages the overall platform and can:

- View registered users.
- Approve or reject Shop Owner accounts.
- Create users manually.
- Suspend or reactivate users.
- Monitor platform activity.

### Shop Owner

A Shop Owner manages their own shop and can:

- Configure shop information.
- Manage categories, products, and product variants.
- Manage inventory and stock adjustments.
- Configure delivery zones and fees.
- Configure accepted payment methods.
- View customers and orders.
- Update order and payment statuses.
- View inventory history and low-stock warnings.

### Customer

Customers do not require accounts. They can:

- Browse a shop’s public catalog.
- View product details and available variants.
- Add available variants to a cart.
- Complete guest checkout.
- Select delivery or pickup.
- Select an available payment method.
- Place an order.
- Track an order using a tracking link or token.

## 2. Authentication and account status

Ordira uses email-based authentication.

Users have one of the following roles:

- `ADMIN`
- `SHOP_OWNER`

Users also have one of the following statuses:

- `PENDING`
- `ACTIVE`
- `SUSPENDED`

The system must enforce these rules:

- A newly registered Shop Owner starts with the `PENDING` status.
- A pending user may log in but must be redirected to the pending-approval page.
- A suspended user may log in but must be redirected to the account-suspended page.
- Only active users may access protected application pages.
- User status must be checked on every request.
- Restricted users must still be able to access the logout route.
- Only Platform Admins may access administrative user-management features.

## 3. Shop requirements

An active Shop Owner must be able to create and configure a shop.

A shop contains:

- Name
- Public slug
- WhatsApp contact
- Instagram contact
- Logo
- Pickup availability
- LBP-to-USD exchange rate

Shop data must be isolated. A Shop Owner must never be able to view or modify another owner’s:

- Products
- Categories
- Variants
- Customers
- Orders
- Delivery zones
- Payment methods
- Inventory records

## 4. Category requirements

A Shop Owner must be able to:

- Create categories.
- View active categories.
- Edit categories belonging to their shop.
- Archive categories.

Category names must be unique within the same shop.

Archiving a category must use a soft-delete approach by setting `is_active=False`. Archived categories must not appear in normal category lists or new product forms.

## 5. Product requirements

A Shop Owner must be able to:

- Create products.
- View active products.
- View product details.
- Edit products.
- Archive products.

Each product belongs to:

- One shop
- One category

A product must not be assigned to a category belonging to another shop.

A product contains:

- Name
- Description
- Image
- Category
- Active status

Archived products must not appear in normal product lists or public storefront pages.

## 6. Product variant requirements

A Product can contain multiple Product Variants.

A Product Variant represents a purchasable version of a product, such as:

- Black, Medium
- Black, Large
- White, Medium

A variant contains:

- Color
- Size
- Unit price
- Currency
- Stock quantity
- Low-stock threshold
- Active status

The same color and size combination must not be duplicated within one product.

A Shop Owner must be able to:

- Create variants.
- View variant details.
- Edit variants.
- Delete variants without inventory history.
- Archive variants that have inventory history.

Archived variants must not appear in normal product, inventory, detail, edit, stock-adjustment, or stock-history pages.

## 7. Inventory requirements

Stock quantities must not be edited directly through the standard Product Variant form.

A Shop Owner adjusts stock by entering:

- A positive or negative quantity change
- A reason for the adjustment

Supported reasons include:

- Restock
- Adjustment
- Damage
- Cancellation
- Sale

Every successful stock adjustment must:

1. Update the variant’s stock quantity.
2. Create a corresponding `StockMovement` record.
3. Record the quantity change.
4. Record the reason.
5. Record the user who performed the adjustment.
6. Record the date and time.

The stock update and movement creation must occur in one database transaction.

The system must reject:

- A zero-quantity adjustment.
- An invalid movement reason.
- An adjustment that would create negative stock.
- An adjustment to an archived variant.
- Cross-shop inventory access.

A variant is considered low in stock when:

```text
stock_quantity <= low_stock_threshold
```

Low-stock variants must be visibly identified in owner-facing inventory pages.

## 8. Customer requirements

Customers use guest checkout and do not require Ordira accounts.

A Customer record belongs to one Shop and contains:

- Full name
- Phone number

Phone numbers must be unique within the same shop.

When an order is placed, the system must create a customer or find the existing customer using the shop and phone number.

A customer’s records and order history must remain isolated within that shop.

## 9. Cart and checkout requirements

The cart must store the selected:

- Product Variant
- Quantity

Adding an item to the cart does not reserve stock.

During checkout, the customer provides:

- Full name
- Phone number
- Fulfillment type
- Delivery information when required
- Payment method

When the customer submits the order, the system must check stock again before creating the order.

If sufficient stock is no longer available, the order must be rejected with a clear message.

## 10. Delivery requirements

A Shop Owner must be able to configure delivery zones.

Each delivery zone contains:

- Area name
- Delivery fee
- Active status

Delivery-zone names must be unique within a shop.

For delivery orders:

- The customer must select an active delivery zone.
- The zone must belong to the selected shop.
- A delivery address is required.
- The applicable delivery fee must be added to the order total.

For pickup orders:

- A delivery zone is not required.
- A delivery address is not required.
- The delivery fee must be zero.
- Pickup must be enabled by the shop.

The selected zone name and delivery fee must be saved as snapshots so future configuration changes do not affect existing orders.

## 11. Payment requirements

Each Shop Owner selects the payment methods accepted by their shop.

Supported methods include:

- Cash
- Whish
- OMT
- Bank Transfer

For the MVP, Ordira records payments but does not process funds through an online gateway.

When an order is created:

- The selected method must belong to the order’s shop.
- A Payment record must be created.
- The payment begins with a Pending status.
- The Shop Owner may later update it to Paid.

Payment status must remain independent of order status. For example, an order may be Preparing while its payment is still Pending.

## 12. Order requirements

When the customer selects **Place Order**, Ordira must perform the following operations:

1. Validate checkout information.
2. Validate the selected shop, delivery zone, and payment method.
3. Lock and check the requested Product Variants.
4. Confirm that sufficient stock is available.
5. Create or locate the Customer record.
6. Create the Order.
7. Generate a unique order number and tracking token.
8. Create an Order Item for every selected variant.
9. Save product, variant, price, and delivery snapshots.
10. Deduct the purchased quantities from inventory.
11. Create inventory movement records.
12. Create a Pending Payment record.
13. Create a notification for the Shop Owner.

These operations must occur inside one database transaction. They must all succeed together or fail together.

## 13. Order item requirements

Each Order Item references one Product Variant and stores:

- Product name snapshot
- Size snapshot
- Color snapshot
- Unit price snapshot
- Quantity
- Line total

Snapshots ensure that historical orders remain unchanged when product information or prices are edited later.

## 14. Order status requirements

An order begins with the `NEW` status.

The standard workflow is:

```text
NEW → PREPARING → HANDED_TO_DELIVERY → COMPLETED
```

An eligible order may also become `CANCELLED`.

When cancelling an order:

- A cancellation reason is required.
- Previously deducted stock must be restored.
- A cancellation StockMovement must be created.
- Stock must be restored only once.
- Orders that are already handed to delivery or completed must not be cancelled unless the final business policy explicitly allows it.

## 15. Notification requirements

A successfully created order must generate a notification for the Shop Owner.

A notification must:

- Belong to the appropriate user or shop.
- Identify the related order.
- Indicate whether it has been read.
- Record its creation time.
- Allow the Shop Owner to navigate to the relevant order.

## 16. Order tracking requirements

Every order must have a unique tracking token.

A customer must be able to open a public tracking page without an account and view appropriate order information and the current order status.

The tracking page must not expose private Shop Owner or internal platform information.

## 17. Business rules

| ID | Rule |
|---|---|
| BR-01 | Customers use guest checkout and do not require accounts. |
| BR-02 | Adding an item to the cart does not reserve stock. |
| BR-03 | Stock is checked again when the customer places an order. |
| BR-04 | Stock deduction must be atomic to prevent overselling. |
| BR-05 | An order is created immediately after successful checkout validation. |
| BR-06 | Product and variant information is saved as order snapshots. |
| BR-07 | The delivery fee is saved as an order snapshot. |
| BR-08 | Cancelling an eligible order restores its stock exactly once. |
| BR-09 | Payment status and order status are independent. |
| BR-10 | Business data must be isolated by shop. |
| BR-11 | Final total equals items total plus delivery fee. |
| BR-12 | Pickup orders always have a zero delivery fee. |
| BR-13 | Every inventory change must create a StockMovement record. |
| BR-14 | Inventory quantities must never become negative. |

## 18. Non-functional requirements

### Security

- Protected pages require authentication.
- Role and status restrictions must be enforced server-side.
- Cross-shop access must return a `404` or another safe denial response.
- State-changing actions must use POST requests and CSRF protection.

### Data consistency

- Order creation and inventory adjustments must use database transactions.
- Concurrent inventory changes must lock affected variants.
- Historical order values must use snapshots.
- Inventory history must not be deleted accidentally.

### Usability

- Forms must display clear validation messages.
- Pages must work on desktop and mobile screens.
- Low-stock and account-status conditions must be visually clear.
- The interface should follow the shared Ordira UI system.

### Maintainability

- Business logic should be separated into service functions where appropriate.
- Reusable layouts should use Django template inheritance.
- Shared components should avoid duplicated HTML and CSS.
- Important workflows must be covered by automated tests.

## 19. MVP exclusions

The following items are outside the current MVP unless added by a future ticket:

- Automated payment gateway processing
- Automated WhatsApp order extraction
- Courier-company API integration
- Customer accounts and customer dashboards
- Marketplace functionality across multiple shops
- Advanced reporting and analytics
- Automated refunds