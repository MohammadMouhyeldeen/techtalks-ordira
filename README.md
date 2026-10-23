# Ordira

Ordira is a platform for small online clothing shops that sell through Instagram
and WhatsApp. Each shop gets a public product catalog where guests can browse,
add items to a session cart, and place orders without creating an account.
Merchants manage inventory, customers, orders, payments, and delivery zones from
a private dashboard. A platform admin approves new shop owners, monitors orders
across all shops, and manages subscriptions.

This repository is the full Django monolith developed for the final academic
submission. It is intended for evaluators and new developers.

---

## Features

### Guest customer

- Browse a shop's public catalog filtered by category
- View product details and select size/colour variants (with stock display)
- Session-based cart (add, update, remove)
- Guest checkout: name, phone, delivery zone or pickup, payment method selection
- Atomic stock deduction on order placement
- Order confirmation page with a WhatsApp contact button linking to the shop
- Persistent order-tracking page (revisit by URL at any time)

### Shop owner

- Shop setup wizard (name, slug, logo, WhatsApp number, Instagram handle,
  exchange rate)
- Product and variant management (create, edit, archive; size, colour, price,
  stock, low-stock threshold)
- Manual stock adjustments with a per-variant movement history
- Dashboard summary: total products, total variants, low-stock count
- Order list with status filter; order detail with line items and delivery info
- Order status transitions and cancellation with stock restoration
- Manual payment recording and outstanding-balance tracking
- Invoice PDF download (generated with ReportLab; includes order snapshot,
  payment method, WhatsApp number)
- Customer list and per-customer order history
- Delivery zone management (name, cost, status)
- Payment method settings (enable/disable accepted payment methods per shop)
- Shop settings (logo, contact info, exchange rate)
- In-app notifications (low-stock alerts; unread badge in navbar)

### Platform admin

- Admin dashboard: pending registrations, active accounts, suspended accounts
- Approve, reject, suspend, or reactivate shop owners
- Direct user creation with a one-time set-password link (no email sent; link
  shown on-screen once and expires after `PASSWORD_RESET_TIMEOUT`, default
  3 days)
- Reissue a set-password link for any active account (invalidates the previous
  password and all active sessions)
- Order monitoring across all shops (filterable by shop and status; latest 100)
- Subscription management: create and edit subscriptions per shop; a shop's
  catalog is only public while it has an active subscription

---

## Tech stack

- **Framework:** Django 5.2.17
- **Language:** Python 3.14.6
- **Database:** PostgreSQL 18.6, accessed via psycopg 3.3.5
- **PDF generation:** ReportLab 5.0.1
- **Image handling:** Pillow 12.3.0
- **Environment variables:** python-dotenv 1.2.3
- **Templates:** Django server-rendered templates (no frontend build step)

Developed and tested with the versions listed above.

---

## Quick start (Windows PowerShell)

### Prerequisites

Install before you begin:

- Python 3.14 (developed and tested with 3.14.6)
- PostgreSQL (the project was developed with 18.6)
- Git

### 1. Clone and switch to the development branch

```powershell
git clone https://github.com/MohammadMouhyeldeen/techtalks-ordira.git
cd techtalks-ordira
git switch develop
```

### 2. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Create the PostgreSQL database and user

Run the following SQL in psql or pgAdmin (choose your own password):

```sql
CREATE USER ordira_user WITH PASSWORD 'your_private_password' CREATEDB;
CREATE DATABASE ordira_db OWNER ordira_user;
```

`CREATEDB` is needed because Django creates a temporary test database when you run the tests.

Do not commit or share your database password.

### 5. Create the environment file

```powershell
Copy-Item .env.example .env
```

Open `.env` and set the values:

```
SECRET_KEY=replace_with_a_generated_secret_key
DEBUG=True
DB_NAME=ordira_db
DB_USER=ordira_user
DB_PASSWORD=your_private_password
DB_HOST=localhost
DB_PORT=5432
```

Generate a secret key with:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Paste the output after `SECRET_KEY=`. `SECRET_KEY` is required -- every
`manage.py` command raises a `RuntimeError` if it is missing or empty.

Keep `DEBUG=True` in your local `.env`. When `DEBUG` is not set it defaults to
`False`, and the development server refuses to start because `ALLOWED_HOSTS` is
an empty list in `config/settings.py`.

### 6. Apply migrations

```powershell
python manage.py migrate
```

### 7. Verify the configuration

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
```

Expected output:

```
System check identified no issues (0 silenced).
No changes detected
```

### 8. Seed demo data

```powershell
python manage.py seed_demo_data
```

This command is idempotent (safe to run more than once). **Never run it against
a production or shared database** -- it creates demo accounts with a fixed
password.

### 9. Start the development server

```powershell
python manage.py runserver
```

### 10. Open in the browser

| URL | Description |
|-----|-------------|
| `http://127.0.0.1:8000/` | Landing page |
| `http://127.0.0.1:8000/accounts/login/` | Login |
| `http://127.0.0.1:8000/store/demo-fashion/` | Demo shop public catalog |

### Demo accounts (demo only -- created by `seed_demo_data`)

| Role | Email | Password | Status |
|------|-------|----------|--------|
| Platform admin | `admin@ordira.test` | `DemoPass123!` | Active |
| Shop owner (active subscription) | `active.owner@ordira.test` | `DemoPass123!` | Active |
| Shop owner (no subscription) | `no.subscription.owner@ordira.test` | `DemoPass123!` | Active |
| Shop owner | `pending.owner@ordira.test` | `DemoPass123!` | Pending |
| Shop owner | `suspended.owner@ordira.test` | `DemoPass123!` | Suspended |

After login, admins land on `/accounts/admin-dashboard/` and shop owners land
on `/shops/dashboard/`.

---

## How to create test users

For development and manual testing, create users with the Django shell:

```powershell
python manage.py shell
```

```python
from accounts.models import User

# Active admin
User.objects.create_superuser("admin@example.com", "testpassword123", full_name="Admin")

# Pending shop owner
User.objects.create_user(
    "pending@example.com", "testpassword123",
    full_name="Pending",
    status=User.Status.PENDING,
    role=User.Role.SHOP_OWNER,
)
```

Always use `create_user()` or `create_superuser()` so that passwords are hashed
automatically. For a full set of demo accounts and products, prefer
`python manage.py seed_demo_data` instead.

---

## Admin: create a user directly

1. Log in as an admin and go to `/accounts/admin-dashboard/create-user/`.
2. Enter the new user's full name, email, and role. The account is created
   Active with no password.
3. The next page shows a one-time set-password link **once only**. Copy it and
   deliver it to the user out-of-band (the system does not send email -- the link
   is displayed on-screen to the admin). Reloading the page does not show it
   again.
4. The user opens the link at `/accounts/set-password/<uidb64>/<token>/`,
   chooses a password, and logs in. The link is single-use and expires after
   `PASSWORD_RESET_TIMEOUT` (Django default: 3 days).
5. To recover a forgotten password or invalidate an existing one, use the
   **Reissue Link** button next to any active account on the admin dashboard.
   Reissuing invalidates the user's current password and all active sessions and
   shows a fresh link once.

---

## Environment variables

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `SECRET_KEY` | Yes | -- | `RuntimeError` if missing or empty |
| `DEBUG` | No | `False` | Accepts `1`, `true`, `yes`, `on` (case-insensitive) |
| `DB_NAME` | Yes (in practice) | -- | PostgreSQL database name |
| `DB_USER` | Yes (in practice) | -- | PostgreSQL user |
| `DB_PASSWORD` | Yes (in practice) | -- | PostgreSQL password |
| `DB_HOST` | No | `localhost` | |
| `DB_PORT` | No | `5432` | |

`ALLOWED_HOSTS` is hardcoded as an empty list. The server refuses to start when
`DEBUG=False` because Django rejects requests with an empty `ALLOWED_HOSTS`. See
**Known limitations**.

---

## Running tests

```powershell
python manage.py test
```

The suite takes a few minutes. At the time of writing it contains approximately
559 tests.

---

## Project structure

| Path | Description |
|------|-------------|
| `accounts/` | Custom user model, registration, login, admin dashboard, user approval |
| `shops/` | Shop model, setup, settings, subscriptions, delivery zones, seed command |
| `products/` | Product and variant management, stock movements, storefront views |
| `customers/` | Customer model and merchant customer list/history |
| `orders/` | Order model, checkout, status transitions, merchant order management |
| `payments/` | Payment recording, invoice PDF service |
| `notifications/` | In-app notification model and views |
| `config/` | Django settings, URL configuration, WSGI |
| `templates/` | All HTML templates (server-rendered) |
| `static/` | CSS, JavaScript, and static assets |
| `docs/` | Project documentation (see Documentation) |

---

## Roles and permissions

### Roles

| Role | Description |
|------|-------------|
| `ADMIN` | Platform administrator; manages all shops and users |
| `SHOP_OWNER` | Manages their own shop, products, orders, customers, and payments |

### User statuses

| Status | Meaning |
|--------|---------|
| `PENDING` | Self-registered; awaiting admin approval |
| `ACTIVE` | Approved; can log in and use the system |
| `SUSPENDED` | Blocked; cannot use the system |

### Registration flow

A shop owner self-registers at `/accounts/register/`. The account starts with
status `PENDING`. The user is immediately redirected to a pending-approval page.
An admin approves, rejects, or suspends them from the admin dashboard. On
approval the status becomes `ACTIVE`; the user can then log in and reach their
dashboard.

### Login destinations

| Role and status | Destination after login |
|-----------------|------------------------|
| Admin, Active | `/accounts/admin-dashboard/` |
| Shop owner, Active | `/shops/dashboard/` |
| Any role, Pending | `/accounts/pending-approval/` |
| Any role, Suspended | `/accounts/account-suspended/` |

---

## Database schema

- **Accounts:** User
- **Shops:** Shop, Subscription, DeliveryZone, ShopPaymentMethod
- **Products:** Category, Product, ProductVariant, StockMovement
- **Customers:** Customer
- **Orders:** Order, OrderItem
- **Payments:** Payment, Invoice
- **Notifications:** Notification

The schema includes foreign-key relationships, uniqueness constraints, product
and checkout snapshots, stock tracking, delivery options, and manual payment
tracking.

---

## Uploaded media

Shop logos and product images are stored locally inside the `media/` directory
during development. The `media/` directory is ignored by Git. Only the file
paths are stored in PostgreSQL; uploaded files are not stored in the database.

---

## Known limitations

- **No deployment.** The project runs locally only; no hosting is configured
  and none is required for this submission.
- **`ALLOWED_HOSTS` is an empty list** in `config/settings.py`. Running with
  `DEBUG=False` causes the development server to reject every request. Always
  set `DEBUG=True` locally.
- **Old `SECRET_KEY` in git history.** The development secret key committed
  before SCRUM-110 remains in the git history. Do not use it anywhere.
- **Phone-number migration.** `customers/migrations/0002` normalizes existing
  phone rows. It raises a `RuntimeError` on any row whose stored number cannot
  be normalized (for example, a number saved before the SCRUM-108 fix that has a
  stray zero after `961`). Fresh databases are not affected.
- **Landing page.** Prices, plan names, and testimonial wording are illustrative
  placeholders. The landing page also hardcodes `/static/` paths instead of
  using `{% static %}`.
- **Dead `#` links.** The following links go nowhere and are not implemented:
  - Merchant dashboard sidebar: **Inventory**
  - Merchant dashboard navbar: logo link
  - Merchant footer: **Privacy**, **Terms**, **Help**
  - Landing page footer: **Help center**, **Contact us**, **About**, **Terms**,
    **Privacy**, and three social-media icons (Instagram, WhatsApp, Facebook)
- **Account > Settings and Shop Settings** in the merchant sidebar both point to
  the same page (`/shops/settings/`).
- **`message-warning` has no style.** The base template uses
  `class="message message-{{ message.tags }}"`, but the CSS only defines
  `.message-success` and `.message-error`; `.message-warning` is unstyled.
- **Delivery zone status** is plain text in the zone list (no coloured badge).

### Not built (non-goals)

Staff accounts, customer accounts, online subscription payment, online order
payment, WhatsApp Business API or automatic message capture, AI assistant,
delivery-company integration or live courier tracking, multiple branches per
shop, native mobile app, advanced analytics or accounting, quote PDF,
marketplace features.

---

## Documentation

- [Documentation home](docs/README.md)
- [Requirements](docs/requirements.md)
- [Architecture](docs/architecture.md)
- [Database](docs/database.md)
- [Application interfaces](docs/api.md)
- [Task documentation](docs/tasks/)