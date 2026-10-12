# SCRUM-8 — Django Project and App Structure

**Owner:** Reem Saijary<br>
**Sprint:** Sprint 1<br>
**Date:** September 9, 2026<br>
**Status:** Completed and merged<br>
**Related ticket:** SCRUM-8<br>

## Task objective

The purpose of SCRUM-8 was to create a clean Django foundation for Ordira and divide the project into domain-based applications.

This structure allows team members to work on separate business areas while keeping the project organized and maintainable.

## Technical decisions

- Django 5.2.17 was selected as the project framework.
- `config` was created as the central project-configuration package.
- Python dependencies are managed through `requirements.txt`.
- Local development uses a virtual environment named `.venv`.
- Features are developed on separate Git branches and merged into `develop` through pull requests.
- Initial database migrations were postponed until the Custom User model was implemented.
- Persistent in-app notifications were separated into a dedicated `notifications` application.

## Project structure

The following Django applications were created:

- `accounts`: custom users, roles, account status, and authentication
- `shops`: shop profiles, owners, staff relationships, delivery zones, and shop settings
- `products`: categories, products, variants, prices, and inventory
- `customers`: customer records belonging to individual shops
- `orders`: orders, order items, delivery information, and order statuses
- `payments`: payment records, payment methods, and outstanding balances
- `notifications`: persistent notifications, including read and unread status
- `config`: shared Django settings and the main URL configuration

This domain-based structure separates the project by responsibility and reduces unnecessary coupling between features.

## Files and components added

The task introduced:

- The Django project configuration
- `manage.py`
- Seven initial domain applications
- `.gitignore`
- `requirements.txt`

All domain applications were registered in `INSTALLED_APPS`.

## Validation

The project configuration was checked using:

```powershell
python manage.py check
```

The result was:

```text
System check identified no issues (0 silenced).
```

This confirmed that Django recognized the project configuration and installed applications without errors.

## Migration decision

No migrations were created or applied during this task.

The Custom User model needed to be implemented before generating the initial migrations. This avoided creating migration history based on Django’s default User model and prevented unnecessary migration conflicts later.

PostgreSQL configuration, the environment example, database design, authentication, and shared user-interface components were handled through separate Sprint 1 tickets.

## Final result

Ordira received a working Django foundation with clearly separated domain applications.

The structure provided the team with a stable starting point for implementing authentication, shops, products, inventory, customers, orders, payments, and notifications in later tasks.