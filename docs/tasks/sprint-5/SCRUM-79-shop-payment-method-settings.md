# SCRUM-79 — Shop Payment Methods Settings
Owner:Jinane Al Ammar

## 1. Overview

SCRUM-79 adds merchant-facing payment method settings so shop owners can control which payment methods their storefront accepts.

The supported payment methods are:

* Cash
* Whish
* OMT
* Bank Transfer

The settings are scoped to the logged-in owner's shop. Checkout already filters payment methods by their enabled state, so the task adds the missing merchant management interface and the required behavior when no payment methods are enabled.

## 2. Objective

Previously, `ShopPaymentMethod` rows could exist for a shop, but there was no merchant-facing interface for owners to enable or disable payment methods.

This task provides:

* an owner-scoped payment method settings page
* enable/disable toggles for all supported payment methods
* default Cash activation for newly created shops
* checkout protection when no payment methods are enabled
* shop isolation so owners cannot access or modify another shop's payment methods

## 3. Supported Payment Methods

The existing `ShopPaymentMethod.MethodName` choices are used:

| Value           | Display name  |
| --------------- | ------------- |
| `CASH`          | Cash          |
| `WHISH`         | Whish         |
| `OMT`           | OMT           |
| `BANK_TRANSFER` | Bank Transfer |

No new database model or migration was required.

## 4. Implementation

### 4.1 Payment Method Settings Form

**File:**

```text
shops/forms.py
```

A new `PaymentMethodSettingsForm` was added.

The form:

* displays all four supported payment methods as enable/disable checkboxes
* loads the current state of the shop's existing `ShopPaymentMethod` rows
* defaults missing Cash configuration to enabled
* defaults missing non-Cash methods to disabled
* saves all four method states using `update_or_create`
* performs the save inside a database transaction

The form requires a shop instance when saving.

### 4.2 Owner-Scoped Settings View

**File:**

```text
shops/views.py
```

A new `payment_method_settings` view was added.

The view uses:

```python
get_owner_shop(request, shop_pk)
```

to guarantee that the requested shop belongs to the logged-in user.

Behavior:

* authenticated owner of the shop → allowed
* another shop → HTTP 404
* non-owner → HTTP 404
* admin → HTTP 404
* anonymous user → redirected to login
* valid POST → payment methods saved and success message displayed

The view does not permit cross-shop access or editing.

### 4.3 URL

**File:**

```text
shops/urls.py
```

The payment settings page is available through the owner-scoped route:

```text
shops/<shop_pk>/payment-methods/
```

with the URL name:

```text
shops:payment-method-settings
```

### 4.4 Payment Method Settings Template

**File:**

```text
templates/shops/payment_method_settings.html
```

A dedicated settings page was added with toggle controls for:

* Cash
* Whish
* OMT
* Bank Transfer

The page follows the existing shop-settings visual structure and includes CSRF protection.

### 4.5 Sidebar Integration

**File:**

```text
templates/components/sidebar.html
```

The existing Payment Methods placeholder was replaced with a link to the new owner-scoped payment settings page.

The link is shown only when a shop is available and receives the active sidebar state when the payment-method settings page is open.

## 5. New Shop Default

A newly created shop starts with:

```text
Cash          enabled
Whish         disabled
OMT           disabled
Bank Transfer disabled
```

This is implemented in the existing shop setup flow.

When the shop is successfully created, a `ShopPaymentMethod` row for Cash is created inside the same database transaction.

This makes the product decision explicit: **Cash is the default payment method for a new shop.**

## 6. Checkout Behavior

The existing checkout form already filters payment methods using:

```python
shop.payment_methods.filter(enabled=True)
```

SCRUM-79 extends this behavior to handle the case where no payment methods are enabled.

When at least one method is enabled:

* checkout lists only enabled methods
* disabled methods are not offered to customers

When no methods are enabled:

* checkout displays a clear message:

```text
No payment methods are currently available for this shop.
Please contact the shop owner.
```

* the payment method field is not offered as an empty selectable option
* a submitted order is rejected
* no `Order` is created

The existing `create_order()` validation remains responsible for ensuring that a selected payment method belongs to the shop and is enabled.

## 7. Tests

### Payment Method Settings Tests

A dedicated `PaymentMethodSettingsTests` test class covers:

* owner can open payment settings
* owner can enable and disable methods
* another shop's settings return 404
* another shop's methods cannot be edited
* anonymous user is redirected to login
* non-owner cannot access the page
* admin cannot access the page

### New Shop Test

`ShopSetupTests` verifies that a newly created shop receives exactly one payment-method row and that Cash is enabled.

### Checkout Tests

Checkout tests verify:

* only enabled payment methods are listed
* checkout displays a clear message when no methods are enabled
* checkout rejects an order when no methods are enabled
* existing checkout behavior continues to work

## 8. Security and Isolation

Payment-method settings are protected by Django authentication and the existing `get_owner_shop()` helper.

A merchant can only access payment methods belonging to their own shop.

Another shop's payment methods are never displayed or modified.

The settings form uses a POST request for saving and the template includes Django's CSRF token.

## 9. Database / Migration Impact

No database schema changes were introduced.

The migration check was run with:

```powershell
python manage.py makemigrations --check --dry-run
```

Result:

```text
No changes detected
```

Payment method rows are created or updated at runtime using the existing `ShopPaymentMethod` model.

## 10. Validation and Test Results

The focused SCRUM-79 tests passed:

```text
Ran 23 tests
OK
```

The complete project test suite passed:

```text
Ran 404 tests
OK
```

Code-quality validation also passed:

```text
git --no-pager diff --cached --check
```

with no reported errors.

## 11. Files Changed

```text
products/forms.py
products/test_cart.py
shops/forms.py
shops/tests.py
shops/urls.py
shops/views.py
templates/components/sidebar.html
templates/shops/payment_method_settings.html
templates/storefront/checkout.html
docs/SCRUM-79-payment-method-settings.md
```

## 12. Acceptance Criteria

| Acceptance criterion                            | Status |
| ----------------------------------------------- | ------ |
| Owner-scoped payment-method settings page       | ✅      |
| Enable/disable payment methods                  | ✅      |
| Checkout lists only enabled methods             | ✅      |
| Clear behavior when no methods are enabled      | ✅      |
| New shop starts with Cash enabled               | ✅      |
| Other shop's methods are never visible/editable | ✅      |
| Enable/disable tests                            | ✅      |
| Checkout filtering tests                        | ✅      |
| Cross-shop isolation tests                      | ✅      |
| Anonymous access denied                         | ✅      |
| Non-owner access denied                         | ✅      |
| Admin access denied                             | ✅      |
| Full test suite green                           | ✅      |
| Documentation included in the PR                | ✅      |

## 13. Final Result

SCRUM-79 provides shop owners with direct control over the payment methods available on their storefront while preserving shop isolation and the existing checkout validation rules.

The implementation introduces no database schema changes and is covered by focused tests and the full project test suite.
