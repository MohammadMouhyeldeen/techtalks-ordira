# Admin Suspend and Reactivate Active Shop Owners

**Owner:** Jinan

**Sprint:** Sprint 6

**Status:** Implementation in progress; targeted tests passing; broader regression testing pending

**Epic:** SCRUM-29

**Branch:** `feature/admin-suspend-reactivate-shop-owners`

**Target branch:** `develop`

**Reviewer:** Mohammad

**Tester:** Reem

## Objective

Allow platform administrators to suspend active shop-owner accounts and reactivate previously suspended shop owners.

The application already supports `ACTIVE`, `PENDING`, and `SUSPENDED` account statuses. The existing `UserStatusMiddleware` redirects suspended users to their account-suspended page. This task extends the admin actions and dashboard to manage the lifecycle of active shop-owner accounts.

## Admin dashboard actions

The admin dashboard supports the following actions:

- **Suspend:** Displayed for active shop owners in the Active Accounts section.
- **Reactivate:** Displayed for suspended shop owners in a separate Suspended Shop Owners section.

The suspended-owner section lists suspended shop owners and provides a Reactivate action for each eligible account. Pagination is supported independently for this section.

Each action is submitted through a POST form containing a CSRF token. Success messages identify the affected user by name and email.

## Account status transitions

### Suspend

An administrator can suspend a shop owner whose current status is `ACTIVE`.

The suspend action changes the account status to `SUSPENDED`. The operation uses a database transaction and row locking, then checks the current status before applying the transition.

An administrator cannot suspend their own account or another administrator. Targets that are not shop owners or are no longer active are rejected without changing their status.

### Reactivate

An administrator can reactivate a shop owner whose current status is `SUSPENDED`.

The reactivate action changes the account status back to `ACTIVE`. It checks the target role and status before saving the change.

Attempts to reactivate accounts that are not suspended or are not shop owners are rejected without changing their status.

The implementation changes the existing `status` field and does not set `is_active=False`, preserving the application's existing authentication and status-middleware behavior.

## Access control and security

Both actions must satisfy the following requirements:

- Only authenticated administrators may execute them.
- Unauthenticated requests are redirected to login.
- Shop owners and other non-admin users are redirected to their appropriate destination without changing the target account.
- GET requests are rejected; the actions accept POST only.
- CSRF protection is enforced.
- Administrators cannot suspend themselves or other administrator accounts.
- The target's role and current status are revalidated before the status transition.
- Missing users return a not-found response rather than modifying another account.

## Suspended-user access

The existing `UserStatusMiddleware` redirects suspended authenticated users to `accounts:account_suspended` on their next request. Reactivation restores the account to `ACTIVE`, allowing the middleware to permit normal access again.

The suspended account page remains available so affected users can read the notice and log out.

## Public storefront availability

The public storefront previously checked whether a shop had an active subscription, but did not check the shop owner's account status.

The shared `public_shop_required` decorator now checks whether the shop owner is suspended before evaluating subscription eligibility. If the owner is suspended, the existing `storefront/unavailable.html` page is rendered with state `unavailable`.

This guard applies to the catalog, product detail, cart, and checkout views that use the decorator. Consequently, customers cannot browse the suspended shop's public catalog or submit a checkout request that creates an order while the owner remains suspended.

## Automated testing

Targeted tests cover:

- Suspending an active shop owner and verifying the new status.
- Redirecting a suspended owner to the account-suspended page on their next request.
- Reactivating a suspended owner and restoring normal access.
- Showing the Suspend and Reactivate actions in the admin dashboard.
- Preventing shop owners from executing either action.
- Preventing anonymous users from executing either action.
- Rejecting GET requests for both actions.
- Preventing an administrator from suspending themselves or another administrator.
- Enforcing CSRF protection with `Client(enforce_csrf_checks=True)`.
- Displaying the unavailable page for a suspended owner's public catalog.
- Preventing checkout from creating an order when the shop owner is suspended.

The nine targeted `ShopOwnerSuspendReactivateTests` passed. The two targeted storefront tests also passed.

The broader regression suite and full project test suite still need to be run and verified before the pull request is ready.
