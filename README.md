# techtalks-ordira

Ordira is designed primarily for small online clothing shops that sell through Instagram and WhatsApp. It provides each shop with a public catalog where customers can browse products, select available variants, place orders as guests, and track their orders. It also helps merchants manage inventory, customer records, orders, delivery status, and manual payments in one place.

## Prerequisites

Before running the project locally, install:

* Python 3.14 or a compatible version
* PostgreSQL
* Git

pgAdmin is optional, but it provides a graphical interface for managing PostgreSQL.

## Local Setup

### 1. Clone the repository

```powershell
git clone https://github.com/MohammadMouhyeldeen/techtalks-ordira.git
cd techtalks-ordira
```

### 2. Switch to the development branch

```powershell
git switch develop
git pull origin develop
```

### 3. Create a virtual environment

```powershell
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Install the Python dependencies

```powershell
python -m pip install -r requirements.txt
```

### 5. Create the PostgreSQL database

Using pgAdmin or the PostgreSQL command-line tools, create:

* A PostgreSQL user named `ordira_user`
* A database named `ordira_db`
* Set `ordira_user` as the owner of `ordira_db`

Each developer should create and securely store their own local database password.

Example SQL:

```sql
CREATE USER ordira_user WITH PASSWORD 'your_private_password';
CREATE DATABASE ordira_db OWNER ordira_user;
```

Do not commit or share the real database password.

### 6. Create the environment file

Copy `.env.example` to a new file named `.env`:

```powershell
Copy-Item .env.example .env
```

Open `.env` and replace the placeholder password with your local PostgreSQL password:

```env
DB_NAME=ordira_db
DB_USER=ordira_user
DB_PASSWORD=your_private_password
DB_HOST=localhost
DB_PORT=5432
```

The `.env` file contains private credentials and is ignored by Git. Never commit it.

The `.env.example` file contains only safe example values and remains in the repository to show developers which environment variables are required.

### 7. Apply the database migrations

Create the required tables in the local PostgreSQL database:

```powershell
python manage.py migrate
```

### 8. Verify the Django configuration

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
```

Expected results:

```text
System check identified no issues
No changes detected
```

### 9. Run the development server

```powershell
python manage.py runserver
```

Open the application at:

```text
http://127.0.0.1:8000/
```

## Database Schema

The initial Ordira database schema includes:

- **Accounts:** User
- **Shops:** Shop, Subscription, DeliveryZone, ShopPaymentMethod
- **Products:** Category, Product, ProductVariant, StockMovement
- **Customers:** Customer
- **Orders:** Order, OrderItem
- **Payments:** Payment, Invoice
- **Notifications:** Notification

The schema includes foreign-key relationships, uniqueness constraints, product and checkout snapshots, stock tracking, delivery options, and manual payment tracking.

## Uploaded Media

Shop logos and product images are stored locally inside the `media/` directory during development.

The `media/` directory is ignored by Git. Only the file paths are stored in PostgreSQL; uploaded image files are not stored directly in the database.


## New URLs available: /register/, /login/, /logout/, /admin-dashboard/ (placeholder), shops:dashboard (placeholder)

## New settings added: LOGIN_URL and LOGIN_REDIRECT_URL in config/settings.py 

## Known limitation flag: both admin_dashboard.html and shops/dashboard.html are explicit placeholders, not real pages yet.

## How to run the new tests: python manage.py test accounts -v2

## How to create test users
During development and manual testing, you may need users with specific roles and statuses (e.g. PENDING, SUSPENDED, ACTIVE ADMIN, ACTIVE SHOP_OWNER). 
To create them properly, use the Django shell:
```bash
python manage.py shell
```
Then paste the following code to seed the test users:
```python
from accounts.models import User

# Example: Create an active admin
User.objects.create_superuser("admin@example.com", "testpassword123", full_name="Admin")

# Example: Create a pending shop owner
User.objects.create_user("pending@example.com", "testpassword123", full_name="Pending", status=User.Status.PENDING, role=User.Role.SHOP_OWNER)
```
*Note: Always use `User.objects.create_user()` or `create_superuser()` to ensure passwords are automatically hashed. Never set passwords directly without hashing.*

### Admin: create a user directly
- `accounts:admin_create_user` (`admin-dashboard/create-user/`, Admin only): enter name, email and role. The account is created ACTIVE with no password.
- The next page shows a one-time set-password link exactly once. Copy it and send it to the user. Reloading does not show it again.
- The user opens the link, chooses a password, then logs in. The link works once and expires after `PASSWORD_RESET_TIMEOUT` (3 days).
