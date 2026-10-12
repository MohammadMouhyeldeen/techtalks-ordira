# SCRUM-9 — PostgreSQL and Environment Configuration

**Owner:** Reem Saijary<br>
**Sprint:** Sprint 1<br>
**Status:** Completed and merged<br>
**Related ticket:** SCRUM-9<br>

## Task objective

The purpose of SCRUM-9 was to configure Ordira to use PostgreSQL and securely load database credentials from environment variables.

## Why PostgreSQL was selected

The initial Django project used SQLite, which stores data in a local file.

PostgreSQL was selected because Ordira is a multi-user business application with many related entities, including shops, products, variants, customers, orders, payments, and notifications.

PostgreSQL provides reliable support for:

- Structured relational data
- Database constraints
- Concurrent users
- Transactions
- Data integrity
- Future deployment requirements

## Local PostgreSQL setup

PostgreSQL 17 and pgAdmin 4 were installed locally.

The following local database resources were created:

- **Database server:** Local PostgreSQL 17
- **Host:** `localhost`
- **Port:** `5432`
- **Database name:** `ordira_db`
- **Database user:** `ordira_user`

The database password is private and is not stored in the repository or documentation.

Each developer must configure their own local PostgreSQL installation and credentials.

## Local installation issue

During the Windows installation, Smart App Control blocked PostgreSQL’s `initdb.exe` file.

As a result:

- The PostgreSQL database cluster was not initialized.
- The PostgreSQL Windows service was not created.
- pgAdmin could not connect to the local database server.

The local issue was resolved by:

1. Temporarily disabling Smart App Control.
2. Initializing the PostgreSQL database cluster manually.
3. Registering PostgreSQL as a Windows service.
4. Starting the service and confirming that it was running.
5. Connecting pgAdmin to the local PostgreSQL server.
6. Re-enabling Smart App Control.

This was a local Windows installation problem and was not caused by the Django project.

## Python dependencies

The following packages were added to `requirements.txt`:

- `psycopg[binary]`: enables Django to communicate with PostgreSQL.
- `python-dotenv`: loads environment variables from a local `.env` file.

Adding these packages to `requirements.txt` allows every developer to install the required dependencies in their virtual environment.

## Environment variables

A local `.env` file was created in the project root with the following structure:

```env
DB_NAME=ordira_db
DB_USER=ordira_user
DB_PASSWORD=your_private_password
DB_HOST=localhost
DB_PORT=5432
```

Each developer must replace the placeholder values with their own local database credentials.

The real `.env` file is excluded through `.gitignore`. Therefore, passwords and other private values are not committed to Git or pushed to GitHub.

## Django configuration

The database configuration in `config/settings.py` was changed from SQLite to PostgreSQL.

The environment file is loaded using `python-dotenv`:

```python
import os

from dotenv import load_dotenv

load_dotenv(BASE_DIR / ".env")
```

Django reads the database configuration from environment variables:

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}
```

This approach keeps sensitive credentials outside the source code while allowing Django to connect to each developer’s local database.

## Validation

The Django configuration was checked using:

```powershell
python manage.py check
```

The system check completed successfully.

A direct database-connection test returned:

```text
Connected to: postgresql ordira_db
```

This confirmed that:

- The PostgreSQL service was running.
- Django loaded the environment variables correctly.
- The configured database user could authenticate.
- Django could connect to `ordira_db`.

## Repository changes

The following files were committed:

- `config/settings.py`
- `requirements.txt`

The following local resources were intentionally excluded:

- `.env`
- Database passwords
- PostgreSQL data files
- Local PostgreSQL installation files

## Migration decision

No migrations were created or applied during SCRUM-9.

Initial migrations were postponed until the Custom User model and required database models were finalized. This prevented unnecessary or conflicting migration history.

## Final result

Ordira was configured to connect securely to a local PostgreSQL database using environment variables.

The project no longer depends on SQLite for development, and private database credentials remain outside the Git repository.