# SCRUM-38 — User Status Enforcement Middleware

**Owner:** Reem Saijary
**Sprint:** Sprint 2
**Status:** Completed and merged
**Related ticket:** SCRUM-38
**Branch:** `feature/scrum-38-status-middleware`
**Target branch:** `develop`



## Task objective

The purpose of this task was to enforce the status of every authenticated user on every request.

Ordira users can have one of these statuses:

- **ACTIVE:** The user can access the application normally.
- **PENDING:** The user is redirected to a pending-approval page.
- **SUSPENDED:** The user is redirected to an account-suspended page.

Checking the status on every request ensures that a user is restricted immediately if an administrator changes their status while they are already logged in.

## Why middleware was used

Django middleware runs automatically for every request.

Using middleware provides centralized status enforcement instead of requiring developers to remember to add a decorator to every protected view.

The request flow is:

1. Django authenticates the user.
2. The status middleware checks `request.user.status`.
3. ACTIVE users continue to the requested page.
4. PENDING users are redirected to the pending-approval page.
5. SUSPENDED users are redirected to the account-suspended page.

The status and logout routes are excluded from enforcement to prevent redirect loops and allow restricted users to log out.

## Implementation

### Status middleware

Created `accounts/middleware.py`.

The middleware:

- Ignores anonymous visitors.
- Allows ACTIVE users to continue normally.
- Redirects PENDING users to `accounts:pending_approval`.
- Redirects SUSPENDED users to `accounts:account_suspended`.
- Allows the status pages and logout routes to load without another redirect.
- Checks the user’s current status again on every request.

### Middleware registration

Updated `config/settings.py` to register the status middleware after Django’s authentication middleware.

This ordering is required because `AuthenticationMiddleware` must identify `request.user` before the status middleware can inspect it.

### Views and URLs

Updated `accounts/views.py` and created `accounts/urls.py`.

The following named routes were added:

- `accounts:pending_approval`
- `accounts:account_suspended`

The account URL configuration was included in `config/urls.py`.

### Templates

Created:

- `templates/accounts/pending_approval.html`
- `templates/accounts/account_suspended.html`

These pages explain why access is restricted and allow the user to log out.

## Automated testing

Seven automated tests were added to `accounts/tests.py`.

The tests verify that:

- Anonymous visitors are not restricted.
- ACTIVE users can access the requested page.
- PENDING users are redirected correctly.
- SUSPENDED users are redirected correctly.
- Restricted users can access their corresponding status page.
- Restricted users can still log out.
- A logged-in user’s status is checked again on the next request after it changes.

## Verification results

The following checks were completed:

- `python manage.py check`
- `python manage.py makemigrations --check --dry-run`
- `python manage.py test accounts`
- `python manage.py test`
- `git diff --check`

All seven account middleware tests passed, the complete test suite passed, no model changes or migrations were required, and no whitespace errors remained.

## Files changed

- `accounts/middleware.py`
- `accounts/urls.py`
- `accounts/views.py`
- `accounts/tests.py`
- `config/settings.py`
- `config/urls.py`
- `templates/accounts/pending_approval.html`
- `templates/accounts/account_suspended.html`

## Final result

User account status is now enforced globally on every request.

This provides the status-control foundation required by the registration, login, logout, redirect, and admin-approval features in the following authentication tasks.