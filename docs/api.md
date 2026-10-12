# Ordira Web Routes and HTTP Behavior

Ordira is currently a server-rendered Django application.

It does not expose a public REST API in the MVP. Its interfaces are implemented through Django URL patterns, views, forms, templates, redirects, and session-based authentication.

This document describes the important route groups, HTTP methods, access rules, and response behavior.

## 1. URL architecture

The main project URL configuration is located in:

```text
config/urls.py
```

Application-specific URL configurations are separated by domain:

```text
accounts/urls.py
shops/urls.py
products/urls.py
```

Additional URL files may be added for Orders, Payments, Customers, and Notifications as their interfaces are implemented.

Named Django routes should be used instead of hardcoded URLs.

Example:

```django
{% url "products:product-list" shop_pk=shop.pk %}
```

## 2. HTTP method conventions

Ordira follows these HTTP conventions:

| Method | Purpose |
|---|---|
| `GET` | Display pages, lists, details, and forms |
| `POST` | Submit forms or perform state-changing actions |

State-changing operations must not be performed using GET requests.

Examples of POST-only actions include:

- Logging out
- Approving or rejecting a user
- Archiving a Category
- Archiving a Product
- Deleting or archiving a Product Variant
- Adjusting inventory
- Updating an Order status
- Cancelling an Order
- Updating a Payment status

POST requests must include Django CSRF protection.

```django
<form method="post">
    {% csrf_token %}
</form>
```

## 3. Authentication routes

The following routes belong to the `accounts` namespace.

| URL | Route name | Method | Access |
|---|---|---|---|
| `/accounts/register/` | `accounts:register` | GET, POST | Anonymous users |
| `/accounts/login/` | `accounts:login` | GET, POST | Anonymous users |
| `/accounts/logout/` | `accounts:logout` | POST | Authenticated users |
| `/accounts/pending-approval/` | `accounts:pending_approval` | GET | Pending users |
| `/accounts/account-suspended/` | `accounts:account_suspended` | GET | Suspended users |

### Registration

`GET /accounts/register/`

Displays the registration form.

`POST /accounts/register/`

Validates the submitted data and creates a new Shop Owner with a Pending status.

A successful registration redirects the user to the appropriate pending-approval flow.

### Login

`GET /accounts/login/`

Displays the login form.

`POST /accounts/login/`

Authenticates the user using email and password.

After login, the redirect depends on role and status:

| User condition | Destination |
|---|---|
| Pending | Pending-approval page |
| Suspended | Account-suspended page |
| Active Platform Admin | Admin dashboard |
| Active Shop Owner with a Shop | Shop dashboard |
| Active Shop Owner without a Shop | Shop setup |

### Logout

Logout is a state-changing operation and should use POST.

Restricted users must remain able to access the logout route.

## 4. Administrative account routes

These routes require an authenticated Platform Admin.

| URL | Route name | Method |
|---|---|---|
| `/accounts/admin-dashboard/` | `accounts:admin_dashboard` | GET |
| `/accounts/admin-dashboard/approve/<id>/` | `accounts:approve_user` | POST |
| `/accounts/admin-dashboard/reject/<id>/` | `accounts:reject_user` | POST |
| `/accounts/admin-dashboard/create-user/` | `accounts:admin_create_user` | GET, POST |
| `/accounts/admin-dashboard/link-display/` | `accounts:admin_link_display` | GET |

A non-admin user must not be allowed to perform administrative operations.

## 5. Shop routes

### Shop setup

| URL | Method | Access |
|---|---|---|
| `/shops/setup/` | GET, POST | Active Shop Owner without a Shop |

`GET` displays the Shop setup form.

`POST` validates and creates the Shop.

The setup workflow collects information such as:

- Shop name
- Public slug
- Contact information
- Pickup availability
- Exchange rate

### Shop dashboard and settings

Shop dashboard and settings pages require:

- An authenticated user
- An Active account
- The Shop Owner role
- Ownership of the requested Shop

A Shop Owner must not be able to access another owner’s dashboard or settings by changing a URL identifier.

## 6. Category routes

Category routes belong to the `products` namespace.

| URL pattern | Route name | Method |
|---|---|---|
| `/shops/<shop_pk>/categories/` | `products:category-list` | GET |
| `/shops/<shop_pk>/categories/create/` | `products:category-create` | GET, POST |
| `/shops/<shop_pk>/categories/<category_pk>/edit/` | `products:category-edit` | GET, POST |
| `/shops/<shop_pk>/categories/<category_pk>/archive/` | `products:category-archive` | POST |

All routes require an authenticated Shop Owner who owns the selected Shop.

### Category list

Displays active Categories belonging to the Shop.

### Category create and edit

`GET` displays the Category form.

`POST` validates and saves the Category.

Invalid forms are rendered again with clear validation messages.

### Category archive

Archiving is POST-only.

A successful request sets:

```text
is_active = False
```

and redirects to the Category list.

## 7. Product routes

| URL pattern | Route name | Method |
|---|---|---|
| `/shops/<shop_pk>/products/` | `products:product-list` | GET |
| `/shops/<shop_pk>/products/create/` | `products:product-create` | GET, POST |
| `/shops/<shop_pk>/products/<product_pk>/` | `products:product-detail` | GET |
| `/shops/<shop_pk>/products/<product_pk>/edit/` | `products:product-edit` | GET, POST |
| `/shops/<shop_pk>/products/<product_pk>/archive/` | `products:product-archive` | POST |

Product queries must always be scoped to the selected Shop.

The Product detail page displays only active Product Variants.

Creating or editing a Product must reject a Category belonging to another Shop.

## 8. Product Variant routes

| URL pattern | Route name | Method |
|---|---|---|
| `/shops/<shop_pk>/products/<product_pk>/variants/create/` | `products:variant-create` | GET, POST |
| `/shops/<shop_pk>/products/<product_pk>/variants/<variant_pk>/` | `products:variant-detail` | GET |
| `/shops/<shop_pk>/products/<product_pk>/variants/<variant_pk>/edit/` | `products:variant-edit` | GET, POST |
| `/shops/<shop_pk>/products/<product_pk>/variants/<variant_pk>/delete/` | `products:variant-delete` | POST |

Every Product Variant route verifies the full ownership chain:

```text
Current User → Shop → Product → Product Variant
```

Archived Product Variants are excluded from normal detail and edit routes.

### Variant deletion behavior

A Product Variant without protected history may be permanently deleted.

A Product Variant with StockMovement or Order Item history must be archived by setting:

```text
is_active = False
```

## 9. Inventory routes

| URL pattern | Route name | Method |
|---|---|---|
| `/shops/<shop_pk>/products/<product_pk>/variants/<variant_pk>/stock/adjust/` | `products:variant-stock-adjust` | GET, POST |
| `/shops/<shop_pk>/products/<product_pk>/variants/<variant_pk>/stock/history/` | `products:variant-stock-history` | GET |

### Stock adjustment

`GET` displays the Stock Adjustment form.

`POST` submits:

- `change_qty`
- `reason`

A successful adjustment:

1. Updates the Product Variant’s stock.
2. Creates a StockMovement.
3. Records the authenticated user.
4. Redirects to an appropriate Product or Variant page.

The request is rejected if:

- The quantity change is zero.
- The reason is invalid.
- The result would produce negative stock.
- The variant is archived.
- The variant belongs to another Shop.

### Stock history

Displays StockMovement records newest first.

The page is available only for active Product Variants belonging to the authenticated Shop Owner.

## 10. Public storefront routes

Public storefront routes do not require authentication.

They use a Shop slug to identify the selected storefront.

The public flow includes:

```text
Shop catalog
    → Product detail
    → Cart
    → Checkout
    → Order success
    → Order tracking
```

Public queries must include only:

- Active Shops where applicable
- Active Categories
- Active Products
- Active Product Variants

Private Shop Owner data must never be exposed through public routes.

## 11. Cart behavior

Cart operations select a Product Variant and quantity.

Adding a Variant to the cart must verify that:

- The Product is active.
- The Product Variant is active.
- The Variant belongs to the selected Shop.
- The requested quantity is valid.

The cart does not reserve inventory.

Stock must be checked again during final checkout.

## 12. Checkout behavior

Checkout accepts customer, fulfillment, delivery, and payment information.

A successful Place Order request performs the following work inside one transaction:

1. Validates checkout information.
2. Locks the requested Product Variants.
3. Rechecks inventory.
4. Creates or locates the Customer.
5. Creates the Order.
6. Creates Order Items.
7. Deducts stock.
8. Creates StockMovement records.
9. Creates a Pending Payment.
10. Creates a Shop Owner notification.
11. Redirects to the Order-success page.

If any operation fails, the complete transaction must roll back.

## 13. Order tracking

Every Order has a unique tracking token.

The public tracking route must locate an Order using this token rather than an easily guessed sequential identifier.

The tracking page may display:

- Order number
- Creation date
- Fulfillment type
- Current status
- Appropriate customer-facing order details

It must not expose:

- Administrative data
- Other Orders
- Internal Shop configuration
- Private user information

## 14. Response behavior

### Successful form submission

Successful create, edit, archive, adjustment, and status-update operations normally return an HTTP redirect:

```text
302 Found
```

The destination page may display a Django success message.

### Invalid form submission

Invalid forms are normally rendered again with:

```text
200 OK
```

The response includes field or non-field validation errors.

### Authentication redirect

An unauthenticated user requesting a protected page is redirected to login.

### Status redirect

Pending and Suspended users are redirected by middleware to their corresponding status page.

### Not found

Ordira returns:

```text
404 Not Found
```

when:

- The requested record does not exist.
- A record belongs to another Shop.
- A Product or Product Variant is archived and excluded from the route.
- The ownership chain is invalid.

Using `404` for cross-shop access avoids revealing whether another Shop’s record exists.

### Method not allowed

POST-only views return:

```text
405 Method Not Allowed
```

when accessed using GET.

## 15. Security behavior

Protected routes use server-side access controls.

Important protections include:

- Session-based authentication
- CSRF protection
- Account-status middleware
- Role checks
- Shop ownership checks
- POST-only state-changing actions
- Form validation
- Model validation
- Database constraints

Frontend links and hidden buttons are not security controls. Permission checks must always occur in Django views or services.

## 16. URL naming conventions

Named URLs follow this general pattern:

```text
<domain>-<action>
```

Examples:

- `category-list`
- `category-create`
- `product-detail`
- `product-edit`
- `variant-stock-adjust`
- `variant-stock-history`

Application namespaces prevent naming conflicts:

```text
accounts:login
shops:dashboard
products:product-list
products:variant-stock-adjust
```

## 17. Future REST API

A REST API is not part of the current MVP.

If Ordira later requires a mobile application or third-party integration, Django REST Framework may be introduced with:

- Token-based authentication
- Versioned API URLs
- JSON serializers
- Permission classes
- Pagination
- Rate limiting
- API-specific automated tests

Until then, `api.md` documents the current Django web interface and HTTP contract.