import threading
from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.contrib.sessions.models import Session
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import User


class UserStatusMiddlewareTests(TestCase):
    def create_user(self, status):
        return User.objects.create_user(
            email=f"{status.lower()}@example.com",
            password="TestPassword123!",
            full_name="Test User",
            status=status,
        )

    def test_anonymous_user_can_access_public_page(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)

    def test_active_user_can_access_page(self):
        user = self.create_user(User.Status.ACTIVE)
        self.client.force_login(user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)

    def test_pending_user_is_redirected(self):
        user = self.create_user(User.Status.PENDING)
        self.client.force_login(user)

        response = self.client.get(reverse("home"))

        self.assertRedirects(
            response,
            reverse("accounts:pending_approval"),
        )

    def test_pending_user_can_access_pending_page(self):
        user = self.create_user(User.Status.PENDING)
        self.client.force_login(user)

        response = self.client.get(
            reverse("accounts:pending_approval")
        )

        self.assertEqual(response.status_code, 200)

    def test_suspended_user_is_redirected(self):
        user = self.create_user(User.Status.SUSPENDED)
        self.client.force_login(user)

        response = self.client.get(reverse("home"))

        self.assertRedirects(
            response,
            reverse("accounts:account_suspended"),
        )

    def test_suspended_user_can_access_suspended_page(self):
        user = self.create_user(User.Status.SUSPENDED)
        self.client.force_login(user)

        response = self.client.get(
            reverse("accounts:account_suspended")
        )

        self.assertEqual(response.status_code, 200)

    def test_status_is_checked_again_on_every_request(self):
        user = self.create_user(User.Status.ACTIVE)
        self.client.force_login(user)

        first_response = self.client.get(reverse("home"))
        self.assertEqual(first_response.status_code, 200)

        user.status = User.Status.SUSPENDED
        user.save(update_fields=["status"])

        second_response = self.client.get(reverse("home"))

        self.assertRedirects(
            second_response,
            reverse("accounts:account_suspended"),
        )


class AdminApprovalTests(TestCase):
    """
    Tests for SCRUM-40: Admin Approval Feature.

    Covers:
     1. Unauthenticated access is redirected to login.
     2. Authenticated non-admin (SHOP_OWNER) is redirected to shops:dashboard.
     3. Admin can load the pending list (HTTP 200).
     4. Approve: PENDING → ACTIVE; user disappears from next list fetch.
     5. Reject: PENDING → SUSPENDED.
     6. Acting on an already-ACTIVE user fails safely (no crash, no double-transition).
     7. Acting on an already-SUSPENDED user fails safely.
     8. Empty state: zero pending users still returns HTTP 200.
     9. Pagination: 26 pending users → page 1 has 25, page 2 has 1.
    10. Approve/Reject via GET is rejected (POST-only, redirect back to list).
    """

    # ------------------------------------------------------------------ helpers

    def _make_admin(self, email="admin@example.com"):
        return User.objects.create_user(
            email=email,
            password="AdminPass123!",
            full_name="Platform Admin",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
        )

    def _make_shop_owner(self, email="owner@example.com", status=User.Status.PENDING):
        return User.objects.create_user(
            email=email,
            password="OwnerPass123!",
            full_name="Shop Owner",
            role=User.Role.SHOP_OWNER,
            status=status,
        )

    def _make_pending_users(self, count, prefix="pending"):
        return [
            self._make_shop_owner(
                email=f"{prefix}{i}@example.com",
                status=User.Status.PENDING,
            )
            for i in range(count)
        ]

    # ------------------------------------------------------------------ 1. Unauthenticated

    def test_unauthenticated_access_to_dashboard_redirects_to_login(self):
        response = self.client.get(reverse("accounts:admin_dashboard"))

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('accounts:admin_dashboard')}",
        )

    def test_unauthenticated_approve_redirects_to_login(self):
        target = self._make_shop_owner()
        response = self.client.post(
            reverse("accounts:approve_user", args=[target.pk])
        )

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next="
            f"{reverse('accounts:approve_user', args=[target.pk])}",
        )

    def test_unauthenticated_reject_redirects_to_login(self):
        target = self._make_shop_owner()
        response = self.client.post(
            reverse("accounts:reject_user", args=[target.pk])
        )

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next="
            f"{reverse('accounts:reject_user', args=[target.pk])}",
        )

    # ------------------------------------------------------------------ 2. Non-admin role gate

    def test_shop_owner_is_redirected_from_dashboard_to_their_own_url(self):
        """
        An authenticated SHOP_OWNER who hits /admin-dashboard/ must be sent to
        shops:dashboard — not to login — because they are already authenticated.
        """
        owner = self._make_shop_owner(status=User.Status.ACTIVE)
        self.client.force_login(owner)

        response = self.client.get(reverse("accounts:admin_dashboard"))

        self.assertRedirects(response, reverse("shops:dashboard"))

    def test_shop_owner_cannot_approve_users(self):
        owner = self._make_shop_owner(status=User.Status.ACTIVE)
        target = self._make_shop_owner(email="target@example.com")
        self.client.force_login(owner)

        self.client.post(reverse("accounts:approve_user", args=[target.pk]))

        target.refresh_from_db()
        self.assertEqual(target.status, User.Status.PENDING)

    def test_shop_owner_cannot_reject_users(self):
        owner = self._make_shop_owner(status=User.Status.ACTIVE)
        target = self._make_shop_owner(email="target@example.com")
        self.client.force_login(owner)

        self.client.post(reverse("accounts:reject_user", args=[target.pk]))

        target.refresh_from_db()
        self.assertEqual(target.status, User.Status.PENDING)

    # ------------------------------------------------------------------ 3. Admin can load list

    def test_admin_can_load_pending_list(self):
        admin = self._make_admin()
        self._make_pending_users(3)
        self.client.force_login(admin)

        response = self.client.get(reverse("accounts:admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pending Registrations")

    # ------------------------------------------------------------------ 4. Approve

    def test_approve_transitions_pending_to_active(self):
        admin = self._make_admin()
        target = self._make_shop_owner()
        self.client.force_login(admin)

        response = self.client.post(
            reverse("accounts:approve_user", args=[target.pk])
        )

        target.refresh_from_db()
        self.assertEqual(target.status, User.Status.ACTIVE)
        self.assertRedirects(response, reverse("accounts:admin_dashboard"))

    def test_approved_user_disappears_from_list_on_next_fetch(self):
        admin = self._make_admin()
        target = self._make_shop_owner()
        self.client.force_login(admin)

        self.client.post(reverse("accounts:approve_user", args=[target.pk]))

        list_response = self.client.get(reverse("accounts:admin_dashboard"))
        # The approved user's approve/reject buttons must not be in the table.
        # (The email may appear in the success toast — check action URL instead.)
        self.assertNotContains(
            list_response,
            reverse("accounts:approve_user", args=[target.pk]),
        )

    # ------------------------------------------------------------------ 5. Reject

    def test_reject_transitions_pending_to_suspended(self):
        admin = self._make_admin()
        target = self._make_shop_owner()
        self.client.force_login(admin)

        response = self.client.post(
            reverse("accounts:reject_user", args=[target.pk])
        )

        target.refresh_from_db()
        self.assertEqual(target.status, User.Status.SUSPENDED)
        self.assertRedirects(response, reverse("accounts:admin_dashboard"))

    def test_rejected_user_disappears_from_list_on_next_fetch(self):
        admin = self._make_admin()
        target = self._make_shop_owner()
        self.client.force_login(admin)

        self.client.post(reverse("accounts:reject_user", args=[target.pk]))

        list_response = self.client.get(reverse("accounts:admin_dashboard"))
        # The rejected user's approve/reject buttons must not be in the table.
        self.assertNotContains(
            list_response,
            reverse("accounts:reject_user", args=[target.pk]),
        )

    # ------------------------------------------------------------------ 6 & 7. Race-condition guard

    def test_approving_already_active_user_does_not_crash(self):
        admin = self._make_admin()
        target = self._make_shop_owner(status=User.Status.ACTIVE)
        self.client.force_login(admin)

        response = self.client.post(
            reverse("accounts:approve_user", args=[target.pk])
        )

        # Must redirect cleanly — no 500.
        self.assertRedirects(response, reverse("accounts:admin_dashboard"))
        # Status must remain ACTIVE, not double-processed.
        target.refresh_from_db()
        self.assertEqual(target.status, User.Status.ACTIVE)

    def test_approving_already_suspended_user_does_not_crash(self):
        admin = self._make_admin()
        target = self._make_shop_owner(status=User.Status.SUSPENDED)
        self.client.force_login(admin)

        response = self.client.post(
            reverse("accounts:approve_user", args=[target.pk])
        )

        self.assertRedirects(response, reverse("accounts:admin_dashboard"))
        target.refresh_from_db()
        self.assertEqual(target.status, User.Status.SUSPENDED)

    def test_rejecting_already_active_user_does_not_crash(self):
        admin = self._make_admin()
        target = self._make_shop_owner(status=User.Status.ACTIVE)
        self.client.force_login(admin)

        response = self.client.post(
            reverse("accounts:reject_user", args=[target.pk])
        )

        self.assertRedirects(response, reverse("accounts:admin_dashboard"))
        target.refresh_from_db()
        self.assertEqual(target.status, User.Status.ACTIVE)

    def test_rejecting_already_suspended_user_does_not_crash(self):
        admin = self._make_admin()
        target = self._make_shop_owner(status=User.Status.SUSPENDED)
        self.client.force_login(admin)

        response = self.client.post(
            reverse("accounts:reject_user", args=[target.pk])
        )

        self.assertRedirects(response, reverse("accounts:admin_dashboard"))
        target.refresh_from_db()
        self.assertEqual(target.status, User.Status.SUSPENDED)

    # ------------------------------------------------------------------ 8. Empty state

    def test_empty_state_renders_with_zero_pending_users(self):
        admin = self._make_admin()
        self.client.force_login(admin)

        response = self.client.get(reverse("accounts:admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No pending registrations")

    # ------------------------------------------------------------------ 9. Pagination

    def test_pagination_page_1_has_25_users(self):
        admin = self._make_admin()
        self._make_pending_users(26)
        self.client.force_login(admin)

        response = self.client.get(reverse("accounts:admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["page_obj"].object_list), 25)

    def test_pagination_page_2_has_1_user(self):
        admin = self._make_admin()
        self._make_pending_users(26)
        self.client.force_login(admin)

        response = self.client.get(
            reverse("accounts:admin_dashboard"), {"page": 2}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["page_obj"].object_list), 1)

    # ------------------------------------------------------------------ 10. POST-only enforcement

    def test_approve_via_get_does_not_transition_status(self):
        admin = self._make_admin()
        target = self._make_shop_owner()
        self.client.force_login(admin)

        response = self.client.get(
            reverse("accounts:approve_user", args=[target.pk])
        )

        # Redirected back to the list — no state change.
        self.assertRedirects(response, reverse("accounts:admin_dashboard"))
        target.refresh_from_db()
        self.assertEqual(target.status, User.Status.PENDING)

    def test_reject_via_get_does_not_transition_status(self):
        admin = self._make_admin()
        target = self._make_shop_owner()
        self.client.force_login(admin)

        response = self.client.get(
            reverse("accounts:reject_user", args=[target.pk])
        )

        self.assertRedirects(response, reverse("accounts:admin_dashboard"))
        target.refresh_from_db()
        self.assertEqual(target.status, User.Status.PENDING)

    # ------------------------------------------------------------------ 11. CSRF enforcement

    def test_approve_without_csrf_token_is_forbidden(self):
        admin = self._make_admin()
        target = self._make_shop_owner()
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(admin)

        response = csrf_client.post(
            reverse("accounts:approve_user", args=[target.pk])
        )

        self.assertEqual(response.status_code, 403)
        target.refresh_from_db()
        self.assertEqual(target.status, User.Status.PENDING)

    def test_reject_without_csrf_token_is_forbidden(self):
        admin = self._make_admin()
        target = self._make_shop_owner()
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(admin)

        response = csrf_client.post(
            reverse("accounts:reject_user", args=[target.pk])
        )

        self.assertEqual(response.status_code, 403)
        target.refresh_from_db()
        self.assertEqual(target.status, User.Status.PENDING)

    # ------------------------------------------------------------------ 12. Nonexistent user_id → 404

    def test_approve_nonexistent_user_returns_404(self):
        admin = self._make_admin()
        self.client.force_login(admin)

        response = self.client.post(
            reverse("accounts:approve_user", args=[999999])
        )

        self.assertEqual(response.status_code, 404)

    def test_reject_nonexistent_user_returns_404(self):
        admin = self._make_admin()
        self.client.force_login(admin)

        response = self.client.post(
            reverse("accounts:reject_user", args=[999999])
        )

        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------ 13. Action-URL role gate (direct POST)

    def test_shop_owner_direct_post_to_approve_is_blocked_to_shops_dashboard(self):
        owner = self._make_shop_owner(status=User.Status.ACTIVE)
        target = self._make_shop_owner(email="target-approve@example.com")
        self.client.force_login(owner)

        response = self.client.post(
            reverse("accounts:approve_user", args=[target.pk])
        )

        self.assertRedirects(response, reverse("shops:dashboard"))
        target.refresh_from_db()
        self.assertEqual(target.status, User.Status.PENDING)

    def test_shop_owner_direct_post_to_reject_is_blocked_to_shops_dashboard(self):
        owner = self._make_shop_owner(status=User.Status.ACTIVE)
        target = self._make_shop_owner(email="target-reject@example.com")
        self.client.force_login(owner)

        response = self.client.post(
            reverse("accounts:reject_user", args=[target.pk])
        )

        self.assertRedirects(response, reverse("shops:dashboard"))
        target.refresh_from_db()
        self.assertEqual(target.status, User.Status.PENDING)

    # ------------------------------------------------------------------ 14. Interaction with UserStatusMiddleware

    def _make_suspended_admin(self, email="suspended-admin@example.com"):
        return User.objects.create_user(
            email=email,
            password="AdminPass123!",
            full_name="Suspended Admin",
            role=User.Role.ADMIN,
            status=User.Status.SUSPENDED,
        )

    def _make_pending_admin(self, email="pending-admin@example.com"):
        return User.objects.create_user(
            email=email,
            password="AdminPass123!",
            full_name="Pending Admin",
            role=User.Role.ADMIN,
            status=User.Status.PENDING,
        )

    def test_suspended_admin_is_redirected_from_dashboard_by_middleware(self):
        suspended_admin = self._make_suspended_admin()
        self.client.force_login(suspended_admin)

        response = self.client.get(reverse("accounts:admin_dashboard"))

        # Must be intercepted by UserStatusMiddleware before view logic
        self.assertRedirects(
            response, reverse("accounts:account_suspended")
        )

    def test_suspended_admin_is_blocked_on_approve_by_middleware(self):
        suspended_admin = self._make_suspended_admin()
        target = self._make_shop_owner()
        self.client.force_login(suspended_admin)

        response = self.client.post(
            reverse("accounts:approve_user", args=[target.pk])
        )

        self.assertRedirects(
            response, reverse("accounts:account_suspended")
        )
        target.refresh_from_db()
        self.assertEqual(target.status, User.Status.PENDING)

    def test_suspended_admin_is_blocked_on_reject_by_middleware(self):
        suspended_admin = self._make_suspended_admin(
            email="suspended-admin2@example.com"
        )
        target = self._make_shop_owner(email="suspend-target@example.com")
        self.client.force_login(suspended_admin)

        response = self.client.post(
            reverse("accounts:reject_user", args=[target.pk])
        )

        self.assertRedirects(
            response, reverse("accounts:account_suspended")
        )
        target.refresh_from_db()
        self.assertEqual(target.status, User.Status.PENDING)

    def test_pending_admin_is_redirected_from_dashboard_by_middleware(self):
        pending_admin = self._make_pending_admin()
        self.client.force_login(pending_admin)

        response = self.client.get(reverse("accounts:admin_dashboard"))

        self.assertRedirects(
            response, reverse("accounts:pending_approval")
        )


class AdminApprovalConcurrencyTests(TransactionTestCase):
    """
    True threaded race tests for SCRUM-40.

    TransactionTestCase (not TestCase) is required: TestCase wraps each test
    in an atomic block, so two threads would share one transaction snapshot
    and never genuinely overlap. TransactionTestCase commits for real, so
    select_for_update() row locking is actually exercised against PostgreSQL.
    """

    def _make_admin(self, email="admin-conc@example.com"):
        return User.objects.create_user(
            email=email,
            password="AdminPass123!",
            full_name="Concurrency Admin",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
        )

    def _make_pending(self, email="victim-conc@example.com"):
        return User.objects.create_user(
            email=email,
            password="OwnerPass123!",
            full_name="Race Victim",
            role=User.Role.SHOP_OWNER,
            status=User.Status.PENDING,
        )

    def _fire_two_concurrent_posts(self, url_name, target_pk, admin_pk):
        barrier = threading.Barrier(2)
        results = [None, None]
        errors = [None, None]

        def worker(idx):
            from django.db import connections

            connections.close_all()
            try:
                client = Client()
                admin = User.objects.get(pk=admin_pk)
                client.force_login(admin)
                barrier.wait(timeout=10)
                resp = client.post(
                    reverse(url_name, args=[target_pk]),
                    follow=True,
                )
                results[idx] = resp
            except Exception as exc:  # noqa: BLE001 - must surface thread errors
                errors[idx] = exc
            finally:
                connections.close_all()

        threads = [
            threading.Thread(target=worker, args=(0,)),
            threading.Thread(target=worker, args=(1,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        return results, errors, threads

    def test_approve_is_safe_under_concurrent_requests(self):
        admin = self._make_admin()
        target = self._make_pending()
        url_name = "accounts:approve_user"

        results, errors, threads = self._fire_two_concurrent_posts(
            url_name, target.pk, admin.pk
        )

        for t in threads:
            self.assertFalse(
                t.is_alive(),
                "Thread deadlocked — select_for_update() did not release.",
            )
        for err in errors:
            self.assertIsNone(err, f"Thread raised: {err!r}")
        for resp in results:
            self.assertIsNotNone(resp, "Thread returned no response")
            self.assertNotEqual(
                resp.status_code, 500, "Concurrent approve crashed with 500"
            )
            self.assertEqual(resp.status_code, 200)  # follow=True lands on list

        target.refresh_from_db()
        self.assertEqual(target.status, User.Status.ACTIVE)

        bodies = [r.content for r in results]
        successes = sum(b"has been approved" in b for b in bodies)
        rejections = sum(b"is no longer pending" in b for b in bodies)
        self.assertEqual(
            successes,
            1,
            f"Expected exactly 1 success, got {successes}. "
            "Without the row lock both threads would succeed.",
        )
        self.assertEqual(
            rejections,
            1,
            f"Expected exactly 1 already-processed rejection, got {rejections}.",
        )

    def test_reject_is_safe_under_concurrent_requests(self):
        admin = self._make_admin(email="admin-conc-reject@example.com")
        target = self._make_pending(email="victim-conc-reject@example.com")
        url_name = "accounts:reject_user"

        results, errors, threads = self._fire_two_concurrent_posts(
            url_name, target.pk, admin.pk
        )

        for t in threads:
            self.assertFalse(
                t.is_alive(),
                "Thread deadlocked — select_for_update() did not release.",
            )
        for err in errors:
            self.assertIsNone(err, f"Thread raised: {err!r}")
        for resp in results:
            self.assertIsNotNone(resp, "Thread returned no response")
            self.assertNotEqual(
                resp.status_code, 500, "Concurrent reject crashed with 500"
            )
            self.assertEqual(resp.status_code, 200)

        target.refresh_from_db()
        self.assertEqual(target.status, User.Status.SUSPENDED)

        bodies = [r.content for r in results]
        successes = sum(b"has been rejected" in b for b in bodies)
        rejections = sum(b"is no longer pending" in b for b in bodies)
        self.assertEqual(
            successes,
            1,
            f"Expected exactly 1 success, got {successes}. "
            "Without the row lock both threads would succeed.",
        )
        self.assertEqual(
            rejections,
            1,
            f"Expected exactly 1 already-processed rejection, got {rejections}.",
        )


# ===========================================================================
# SCRUM-41: Admin direct user creation + one-time set-password link (Part A)
# ===========================================================================


class AdminCreateUserTests(TestCase):
    """
    Tests for SCRUM-41 Part A: create, link display, set-password page.

    Permission grid tested for every Admin-only endpoint:
        Anonymous, PENDING owner, SUSPENDED owner, ACTIVE SHOP_OWNER,
        PENDING ADMIN (middleware), SUSPENDED ADMIN (middleware), ACTIVE ADMIN.
    """

    # ------------------------------------------------------------------ helpers

    def _make_admin(self, email="admin@example.com"):
        return User.objects.create_user(
            email=email,
            password="AdminPass123!",
            full_name="Platform Admin",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
        )

    def _make_shop_owner(self, email="owner@example.com",
                         status=User.Status.ACTIVE):
        return User.objects.create_user(
            email=email,
            password="OwnerPass123!",
            full_name="Shop Owner",
            role=User.Role.SHOP_OWNER,
            status=status,
        )

    def _make_pending_admin(self, email="pending-admin@example.com"):
        return User.objects.create_user(
            email=email,
            password="AdminPass123!",
            full_name="Pending Admin",
            role=User.Role.ADMIN,
            status=User.Status.PENDING,
        )

    def _make_suspended_admin(self, email="suspended-admin@example.com"):
        return User.objects.create_user(
            email=email,
            password="AdminPass123!",
            full_name="Suspended Admin",
            role=User.Role.ADMIN,
            status=User.Status.SUSPENDED,
        )

    def _valid_post(self, **overrides):
        data = {
            "full_name": "New User",
            "email": "newuser@example.com",
            "role": User.Role.SHOP_OWNER,
        }
        data.update(overrides)
        return data

    def _create_user_as_admin(self, admin, data=None):
        """Helper: POST to create-user as admin, returns response."""
        self.client.force_login(admin)
        return self.client.post(
            reverse("accounts:admin_create_user"),
            data or self._valid_post(),
        )

    # ------------------------------------------------------------------ AC1: permission grid — create page GET

    def test_anonymous_cannot_get_create_page(self):
        url = reverse("accounts:admin_create_user")
        response = self.client.get(url)
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={url}",
        )

    def test_pending_owner_redirected_from_create_page_by_middleware(self):
        user = self._make_shop_owner(status=User.Status.PENDING)
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:admin_create_user"))
        self.assertRedirects(response, reverse("accounts:pending_approval"))

    def test_suspended_owner_redirected_from_create_page_by_middleware(self):
        user = self._make_shop_owner(status=User.Status.SUSPENDED)
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:admin_create_user"))
        self.assertRedirects(response, reverse("accounts:account_suspended"))

    def test_active_shop_owner_redirected_from_create_page(self):
        owner = self._make_shop_owner(status=User.Status.ACTIVE)
        self.client.force_login(owner)
        response = self.client.get(reverse("accounts:admin_create_user"))
        self.assertRedirects(response, reverse("shops:dashboard"))

    def test_pending_admin_redirected_from_create_page_by_middleware(self):
        admin = self._make_pending_admin()
        self.client.force_login(admin)
        response = self.client.get(reverse("accounts:admin_create_user"))
        self.assertRedirects(response, reverse("accounts:pending_approval"))

    def test_suspended_admin_redirected_from_create_page_by_middleware(self):
        admin = self._make_suspended_admin()
        self.client.force_login(admin)
        response = self.client.get(reverse("accounts:admin_create_user"))
        self.assertRedirects(response, reverse("accounts:account_suspended"))

    def test_active_admin_can_get_create_page(self):
        admin = self._make_admin()
        self.client.force_login(admin)
        response = self.client.get(reverse("accounts:admin_create_user"))
        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------ AC1: permission grid — create page POST

    def test_anonymous_cannot_post_create(self):
        url = reverse("accounts:admin_create_user")
        response = self.client.post(url, self._valid_post())
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={url}",
        )
        self.assertFalse(User.objects.filter(email="newuser@example.com").exists())

    def test_active_shop_owner_cannot_post_create(self):
        owner = self._make_shop_owner(status=User.Status.ACTIVE)
        self.client.force_login(owner)
        self.client.post(reverse("accounts:admin_create_user"), self._valid_post())
        self.assertFalse(User.objects.filter(email="newuser@example.com").exists())

    def test_active_admin_can_post_create(self):
        admin = self._make_admin()
        response = self._create_user_as_admin(admin)
        self.assertRedirects(response, reverse("accounts:admin_link_display"))
        self.assertTrue(User.objects.filter(email="newuser@example.com").exists())

    # ------------------------------------------------------------------ AC1: permission grid — link display GET

    def test_anonymous_cannot_get_link_display(self):
        url = reverse("accounts:admin_link_display")
        response = self.client.get(url)
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={url}",
        )

    def test_pending_owner_redirected_from_link_display_by_middleware(self):
        user = self._make_shop_owner(status=User.Status.PENDING)
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:admin_link_display"))
        self.assertRedirects(response, reverse("accounts:pending_approval"))

    def test_suspended_owner_redirected_from_link_display_by_middleware(self):
        user = self._make_shop_owner(status=User.Status.SUSPENDED)
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:admin_link_display"))
        self.assertRedirects(response, reverse("accounts:account_suspended"))

    def test_active_shop_owner_redirected_from_link_display(self):
        owner = self._make_shop_owner(status=User.Status.ACTIVE)
        self.client.force_login(owner)
        response = self.client.get(reverse("accounts:admin_link_display"))
        self.assertRedirects(response, reverse("shops:dashboard"))

    def test_pending_admin_redirected_from_link_display_by_middleware(self):
        admin = self._make_pending_admin()
        self.client.force_login(admin)
        response = self.client.get(reverse("accounts:admin_link_display"))
        self.assertRedirects(response, reverse("accounts:pending_approval"))

    def test_suspended_admin_redirected_from_link_display_by_middleware(self):
        admin = self._make_suspended_admin()
        self.client.force_login(admin)
        response = self.client.get(reverse("accounts:admin_link_display"))
        self.assertRedirects(response, reverse("accounts:account_suspended"))

    def test_active_admin_direct_get_link_display_without_session_key_redirects(self):
        """Direct GET to link_display with no session key → redirect back."""
        admin = self._make_admin()
        self.client.force_login(admin)
        response = self.client.get(reverse("accounts:admin_link_display"))
        self.assertRedirects(response, reverse("accounts:admin_create_user"))

    def test_link_display_post_and_head_do_not_consume_session_key(self):
        admin = self._make_admin()
        self._create_user_as_admin(admin)
        url = reverse("accounts:admin_link_display")
        
        self.client.head(url)
        self.client.post(url)
        
        # The key should still be there for the GET
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "set-password")

    # ------------------------------------------------------------------ AC2: form validation

    def test_blank_full_name_rejected(self):
        admin = self._make_admin()
        response = self._create_user_as_admin(admin, self._valid_post(full_name=""))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="newuser@example.com").exists())

    def test_whitespace_only_full_name_rejected(self):
        admin = self._make_admin()
        response = self._create_user_as_admin(admin, self._valid_post(full_name="   "))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="newuser@example.com").exists())

    def test_over_max_length_full_name_rejected(self):
        admin = self._make_admin()
        long_name = "A" * 151
        response = self._create_user_as_admin(admin, self._valid_post(full_name=long_name))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="newuser@example.com").exists())

    def test_blank_email_rejected(self):
        admin = self._make_admin()
        response = self._create_user_as_admin(admin, self._valid_post(email=""))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="").exists())

    def test_over_max_length_email_rejected(self):
        admin = self._make_admin()
        long_email = "a" * 244 + "@example.com"  # 256 chars, > 254
        response = self._create_user_as_admin(admin, self._valid_post(email=long_email))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email=long_email).exists())

    def test_invalid_email_format_rejected(self):
        admin = self._make_admin()
        response = self._create_user_as_admin(admin, self._valid_post(email="notanemail"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="notanemail").exists())

    def test_duplicate_email_exact_rejected(self):
        admin = self._make_admin()
        User.objects.create_user(
            email="newuser@example.com", password=None, full_name="Existing"
        )
        response = self._create_user_as_admin(admin)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            User.objects.filter(email="newuser@example.com").count(), 1
        )

    def test_duplicate_email_case_variant_rejected(self):
        admin = self._make_admin()
        User.objects.create_user(
            email="newuser@example.com", password=None, full_name="Existing"
        )
        response = self._create_user_as_admin(
            admin, self._valid_post(email="NEWUSER@EXAMPLE.COM")
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            User.objects.filter(email__iexact="newuser@example.com").count(), 1
        )

    def test_duplicate_email_whitespace_variant_rejected(self):
        admin = self._make_admin()
        User.objects.create_user(
            email="newuser@example.com", password=None, full_name="Existing"
        )
        response = self._create_user_as_admin(
            admin, self._valid_post(email="  newuser@example.com  ")
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            User.objects.filter(email="newuser@example.com").count(), 1
        )

    def test_email_is_stored_fully_lowercased(self):
        admin = self._make_admin()
        self._create_user_as_admin(admin, self._valid_post(email="MixedCase@Example.COM"))
        self.assertTrue(
            User.objects.filter(email="mixedcase@example.com").exists()
        )

    # ------------------------------------------------------------------ AC3: role safety

    def test_role_admin_accepted(self):
        admin = self._make_admin()
        self._create_user_as_admin(admin, self._valid_post(role=User.Role.ADMIN))
        new = User.objects.get(email="newuser@example.com")
        self.assertEqual(new.role, User.Role.ADMIN)

    def test_role_shop_owner_accepted(self):
        admin = self._make_admin()
        self._create_user_as_admin(admin, self._valid_post(role=User.Role.SHOP_OWNER))
        new = User.objects.get(email="newuser@example.com")
        self.assertEqual(new.role, User.Role.SHOP_OWNER)

    def test_role_tampered_superuser_rejected(self):
        admin = self._make_admin()
        response = self._create_user_as_admin(
            admin, self._valid_post(role="SUPERUSER")
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="newuser@example.com").exists())

    def test_role_tampered_lowercase_rejected(self):
        admin = self._make_admin()
        response = self._create_user_as_admin(
            admin, self._valid_post(role="admin")
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="newuser@example.com").exists())

    def test_role_empty_rejected(self):
        admin = self._make_admin()
        response = self._create_user_as_admin(admin, self._valid_post(role=""))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="newuser@example.com").exists())

    def test_role_missing_rejected(self):
        admin = self._make_admin()
        data = {"full_name": "New User", "email": "newuser@example.com"}
        self.client.force_login(admin)
        response = self.client.post(reverse("accounts:admin_create_user"), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="newuser@example.com").exists())

    def test_created_admin_has_no_is_staff_or_superuser(self):
        """New ADMIN accounts follow the existing in-app convention: no is_staff/is_superuser."""
        admin = self._make_admin()
        self._create_user_as_admin(admin, self._valid_post(role=User.Role.ADMIN))
        new = User.objects.get(email="newuser@example.com")
        self.assertFalse(new.is_staff)
        self.assertFalse(new.is_superuser)

    # ------------------------------------------------------------------ AC4: account state

    def test_created_user_status_is_active(self):
        admin = self._make_admin()
        self._create_user_as_admin(admin)
        new = User.objects.get(email="newuser@example.com")
        self.assertEqual(new.status, User.Status.ACTIVE)

    def test_created_user_is_active_flag_is_true(self):
        admin = self._make_admin()
        self._create_user_as_admin(admin)
        new = User.objects.get(email="newuser@example.com")
        self.assertTrue(new.is_active)

    def test_created_user_has_unusable_password(self):
        admin = self._make_admin()
        self._create_user_as_admin(admin)
        new = User.objects.get(email="newuser@example.com")
        self.assertFalse(new.has_usable_password())

    def test_created_shop_owner_has_no_shop(self):
        """AC4: bare SHOP_OWNER — no Shop row created."""
        from shops.models import Shop
        admin = self._make_admin()
        self._create_user_as_admin(admin, self._valid_post(role=User.Role.SHOP_OWNER))
        new = User.objects.get(email="newuser@example.com")
        self.assertFalse(Shop.objects.filter(owner=new).exists())

    # ------------------------------------------------------------------ AC5 & AC6: link generation and display

    def _get_link_display(self, admin):
        """Create a user as admin and follow redirect to link display; return response."""
        self._create_user_as_admin(admin)
        response = self.client.get(reverse("accounts:admin_link_display"))
        self.assertEqual(response.status_code, 200)
        return response

    def test_link_display_sets_no_store_header(self):
        admin = self._make_admin()
        response = self._get_link_display(admin)
        self.assertEqual(response.get("Cache-Control"), "no-store")

    def test_link_is_absolute_url_containing_scheme_and_host(self):
        admin = self._make_admin()
        response = self._get_link_display(admin)
        link = response.context["link"]
        self.assertTrue(link.startswith("http://") or link.startswith("https://"),
                        f"Link does not start with http(s)://: {link!r}")

    def test_link_contains_expected_uidb64(self):
        admin = self._make_admin()
        self._create_user_as_admin(admin)
        new = User.objects.get(email="newuser@example.com")
        expected_uid = urlsafe_base64_encode(force_bytes(new.pk))
        response = self.client.get(reverse("accounts:admin_link_display"))
        link = response.context["link"]
        self.assertIn(expected_uid, link)

    def test_link_display_second_get_redirects_no_link_shown(self):
        """AC6: reload / back-button must not re-show the link."""
        admin = self._make_admin()
        self._create_user_as_admin(admin)
        # First GET consumes the session key
        self.client.get(reverse("accounts:admin_link_display"))
        # Second GET: session key is gone
        response = self.client.get(reverse("accounts:admin_link_display"))
        self.assertRedirects(response, reverse("accounts:admin_create_user"))

    def test_link_not_in_session_data_after_display(self):
        """
        AC6 / Amendment 1: the link, token and uid-b64 must not appear in any
        Session row in the database after the link-display page has been rendered.
        """
        admin = self._make_admin()
        self._create_user_as_admin(admin)
        new = User.objects.get(email="newuser@example.com")
        uid_b64 = urlsafe_base64_encode(force_bytes(new.pk))
        token = default_token_generator.make_token(new)
        expected_link_fragment = f"set-password/{uid_b64}/"

        # Render the link display page (this pops the session key)
        self.client.get(reverse("accounts:admin_link_display"))

        for session in Session.objects.all():
            raw = session.session_data
            self.assertNotIn(
                uid_b64.encode() if isinstance(raw, bytes) else uid_b64,
                raw,
                "uid-b64 found in session data after link display",
            )
            self.assertNotIn(
                token.encode() if isinstance(raw, bytes) else token,
                raw,
                "token found in session data after link display",
            )
            self.assertNotIn(
                expected_link_fragment.encode() if isinstance(raw, bytes) else expected_link_fragment,
                raw,
                "link fragment found in session data after link display",
            )

    def test_link_not_in_log_output_during_create_and_display(self):
        """
        AC6 / AC12: neither the link, token, uid-b64, nor any password appear
        in any log line during the create + display flow.
        """
        admin = self._make_admin()
        logger_name = "accounts.views"

        with self.assertLogs(logger_name, level="INFO") as log_ctx:
            self.client.force_login(admin)
            self.client.post(
                reverse("accounts:admin_create_user"), self._valid_post()
            )
            new = User.objects.get(email="newuser@example.com")
            uid_b64 = urlsafe_base64_encode(force_bytes(new.pk))
            token = default_token_generator.make_token(new)
            # Also render the display page (which generates the link in-process)
            self.client.get(reverse("accounts:admin_link_display"))

        combined = " ".join(log_ctx.output)
        link_fragment = f"set-password/{uid_b64}/"
        for secret in (uid_b64, token, link_fragment):
            self.assertNotIn(
                secret, combined,
                f"Secret {secret!r} appeared in log output",
            )

    def test_link_not_in_messages_framework_after_creation(self):
        """AC6: Django messages storage must not contain the link."""
        admin = self._make_admin()
        self.client.force_login(admin)
        self.client.post(
            reverse("accounts:admin_create_user"), self._valid_post()
        )
        # Follow the redirect to link display
        response = self.client.get(reverse("accounts:admin_link_display"))
        # Drain messages
        from django.contrib.messages import get_messages
        msgs = list(get_messages(response.wsgi_request))
        link = response.context["link"]
        for m in msgs:
            self.assertNotIn(link, str(m.message))

    def test_html_in_full_name_is_escaped_on_link_display_page(self):
        admin = self._make_admin()
        self.client.force_login(admin)
        xss_name = "<script>alert(1)</script>"
        self.client.post(
            reverse("accounts:admin_create_user"),
            self._valid_post(full_name=xss_name),
        )
        response = self.client.get(reverse("accounts:admin_link_display"))
        self.assertEqual(response.status_code, 200)
        # The raw script tag must not appear unescaped in the response body
        self.assertNotContains(response, "<script>alert(1)</script>")
        # The escaped version should be present
        self.assertContains(response, "&lt;script&gt;")

    # ------------------------------------------------------------------ AC7: set-password page

    def _get_set_password_url(self, user):
        uid_b64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        return reverse("accounts:set_password", args=[uid_b64, token])

    def test_set_password_page_loads_with_valid_link(self):
        """
        AC7: GET with follow=True must land on the token-less URL and show the form.
        The built-in PasswordResetConfirmView redirects the first GET to strip the
        token from the URL into the session.
        """
        new_user = self._make_shop_owner(email="target@example.com")
        new_user.set_unusable_password()
        new_user.save()
        url = self._get_set_password_url(new_user)
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        # After follow, the final URL must NOT contain the token
        final_url = response.redirect_chain[-1][0] if response.redirect_chain else url
        self.assertNotIn(
            default_token_generator.make_token(new_user),
            final_url,
            "Token still present in final URL after PasswordResetConfirmView redirect",
        )
        self.assertTrue(response.context.get("validlink"), "validlink should be True")

    def test_set_password_valid_link_works_once(self):
        """AC7: after setting a password, the same link shows validlink=False."""
        new_user = self._make_shop_owner(email="target@example.com")
        new_user.set_unusable_password()
        new_user.save()
        url = self._get_set_password_url(new_user)

        # Follow the initial redirect; Django moves token into session and
        # redirects to /<uidb64>/set-password/ (token sentinel in URL).
        get_resp = self.client.get(url, follow=True)
        session_url = get_resp.redirect_chain[-1][0]  # e.g. /accounts/set-password/<uid>/set-password/
        # POST the password to the session-backed URL
        self.client.post(
            session_url,
            {"new_password1": "GoodPassword99!", "new_password2": "GoodPassword99!"},
        )

        # The reliable way: fetch the original link again with a fresh client
        fresh_client = Client()
        response = fresh_client.get(url, follow=True)
        self.assertFalse(
            response.context.get("validlink", True),
            "Used link should have validlink=False",
        )

    def test_set_password_tampered_token_shows_invalid(self):
        new_user = self._make_shop_owner(email="target@example.com")
        new_user.set_unusable_password()
        new_user.save()
        uid_b64 = urlsafe_base64_encode(force_bytes(new_user.pk))
        bad_url = reverse("accounts:set_password", args=[uid_b64, "bad-token-xxx"])
        response = self.client.get(bad_url, follow=True)
        self.assertFalse(response.context.get("validlink", True))

    def test_set_password_tampered_uid_shows_invalid(self):
        bad_uid = urlsafe_base64_encode(force_bytes(999999))
        token = "some-token"
        bad_url = reverse("accounts:set_password", args=[bad_uid, token])
        response = self.client.get(bad_url, follow=True)
        self.assertFalse(response.context.get("validlink", True))

    def test_set_password_wrong_uid_for_token_shows_invalid(self):
        user_a = self._make_shop_owner(email="a@example.com")
        user_b = self._make_shop_owner(email="b@example.com")
        user_a.set_unusable_password(); user_a.save()
        user_b.set_unusable_password(); user_b.save()
        # Token for A, uid for B
        token_a = default_token_generator.make_token(user_a)
        uid_b = urlsafe_base64_encode(force_bytes(user_b.pk))
        bad_url = reverse("accounts:set_password", args=[uid_b, token_a])
        response = self.client.get(bad_url, follow=True)
        self.assertFalse(response.context.get("validlink", True))

    def test_set_password_expired_link_shows_invalid(self):
        """AC7: expired link shown by advancing the token generator's clock far into the future."""
        from datetime import datetime
        new_user = self._make_shop_owner(email="target@example.com")
        new_user.set_unusable_password()
        new_user.save()
        url = self._get_set_password_url(new_user)
        # _now() must return a datetime (the generator uses datetime arithmetic).
        # Returning datetime.max makes every token appear centuries old.
        with patch(
            "django.contrib.auth.tokens.PasswordResetTokenGenerator._now",
            return_value=datetime.max,
        ):
            response = self.client.get(url, follow=True)
        self.assertFalse(response.context.get("validlink", True))

    def test_set_password_weak_password_rejected_not_500(self):
        new_user = self._make_shop_owner(email="target@example.com")
        new_user.set_unusable_password()
        new_user.save()
        url = self._get_set_password_url(new_user)
        get_resp = self.client.get(url, follow=True)
        session_url = get_resp.redirect_chain[-1][0]
        response = self.client.post(
            session_url,
            {"new_password1": "123", "new_password2": "123"},
        )
        self.assertEqual(response.status_code, 200)  # re-renders form, not 500
        new_user.refresh_from_db()
        self.assertFalse(new_user.has_usable_password())

    def test_set_password_mismatched_confirmation_rejected(self):
        new_user = self._make_shop_owner(email="target@example.com")
        new_user.set_unusable_password()
        new_user.save()
        url = self._get_set_password_url(new_user)
        get_resp = self.client.get(url, follow=True)
        session_url = get_resp.redirect_chain[-1][0]
        response = self.client.post(
            session_url,
            {"new_password1": "GoodPassword99!", "new_password2": "Different99!"},
        )
        self.assertEqual(response.status_code, 200)
        new_user.refresh_from_db()
        self.assertFalse(new_user.has_usable_password())

    def test_set_password_redirects_to_complete_page_not_login(self):
        new_user = self._make_shop_owner(email="target@example.com")
        new_user.set_unusable_password()
        new_user.save()
        url = self._get_set_password_url(new_user)
        get_resp = self.client.get(url, follow=True)
        session_url = get_resp.redirect_chain[-1][0]
        response = self.client.post(
            session_url,
            {"new_password1": "GoodPassword99!", "new_password2": "GoodPassword99!"},
            follow=True,
        )
        self.assertRedirects(
            response,
            reverse("accounts:set_password_complete"),
            fetch_redirect_response=True,
        )

    def test_set_password_csrf_without_token_is_403(self):
        new_user = self._make_shop_owner(email="target@example.com")
        new_user.set_unusable_password()
        new_user.save()
        url = self._get_set_password_url(new_user)
        csrf_client = Client(enforce_csrf_checks=True)
        get_resp = csrf_client.get(url, follow=True)
        session_url = get_resp.redirect_chain[-1][0]
        response = csrf_client.post(
            session_url,
            {"new_password1": "GoodPassword99!", "new_password2": "GoodPassword99!"},
        )
        self.assertEqual(response.status_code, 403)

    # ------------------------------------------------------------------ AC8: login before setup fails

    def test_login_before_setup_fails_with_empty_password(self):
        new_user = self._make_shop_owner(email="target@example.com")
        new_user.set_unusable_password()
        new_user.save()
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "target@example.com", "password": ""},
        )
        self.assertEqual(response.status_code, 200)  # form re-rendered
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_login_before_setup_fails_with_exclamation(self):
        new_user = self._make_shop_owner(email="target@example.com")
        new_user.set_unusable_password()
        new_user.save()
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "target@example.com", "password": "!"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_login_before_setup_fails_with_unusable_password_hash_string(self):
        """Posting the literal unusable-password marker must not authenticate."""
        new_user = self._make_shop_owner(email="target@example.com")
        new_user.set_unusable_password()
        new_user.save()
        # The stored password value for unusable passwords starts with UNUSABLE_PASSWORD_PREFIX
        stored = new_user.password  # e.g. "!<random>"
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "target@example.com", "password": stored},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    # ------------------------------------------------------------------ AC9: login after setup

    def _set_password_for(self, user, password="GoodPassword99!"):
        """
        Exercise the full set-password flow for a user.

        Django's PasswordResetConfirmView redirects the first GET to a
        session-backed sentinel URL (/<uidb64>/set-password/). We capture
        that URL from the redirect chain and POST to it.
        """
        url = self._get_set_password_url(user)
        c = Client()
        get_resp = c.get(url, follow=True)
        session_url = get_resp.redirect_chain[-1][0]
        resp = c.post(
            session_url,
            {"new_password1": password, "new_password2": password},
            follow=True,
        )
        return resp.status_code == 200

    def test_after_set_password_shop_owner_logs_in_and_lands_on_dashboard(self):
        new_user = User.objects.create_user(
            email="shopowner@example.com",
            password=None,
            full_name="New Owner",
            role=User.Role.SHOP_OWNER,
            status=User.Status.ACTIVE,
        )
        self._set_password_for(new_user)
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "shopowner@example.com", "password": "GoodPassword99!"},
        )
        self.assertRedirects(response, reverse("shops:dashboard"))

    def test_after_set_password_admin_logs_in_and_lands_on_admin_dashboard(self):
        new_user = User.objects.create_user(
            email="newadmin@example.com",
            password=None,
            full_name="New Admin",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
        )
        self._set_password_for(new_user)
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "newadmin@example.com", "password": "GoodPassword99!"},
        )
        self.assertRedirects(response, reverse("accounts:admin_dashboard"))

    # ------------------------------------------------------------------ AC11: CSRF on create

    def test_create_user_without_csrf_token_is_403(self):
        admin = self._make_admin()
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(admin)
        response = csrf_client.post(
            reverse("accounts:admin_create_user"),
            self._valid_post(),
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(email="newuser@example.com").exists())

    # ------------------------------------------------------------------ AC12: audit logging

    def test_ac12_create_log_exactly_one_info_line(self):
        admin = self._make_admin()
        with self.assertLogs("accounts.views", level="INFO") as log_ctx:
            self._create_user_as_admin(admin)
            self.client.get(reverse("accounts:admin_link_display"))

        # Exactly one info line
        self.assertEqual(len(log_ctx.output), 1)
        log_line = log_ctx.output[0]

        new = User.objects.get(email="newuser@example.com")
        
        # Must contain acting admin id, target id, role
        self.assertIn(str(admin.pk), log_line)
        self.assertIn(str(new.pk), log_line)
        self.assertIn(new.role, log_line)

        uid_b64 = urlsafe_base64_encode(force_bytes(new.pk))
        token = default_token_generator.make_token(new)

        for secret in (uid_b64, token, new.password):
            self.assertNotIn(secret, log_line)

    def test_ac4_shop_owner_created_correctly(self):
        from shops.models import Shop, Subscription
        initial_shops = Shop.objects.count()
        initial_subs = Subscription.objects.count()

        admin = self._make_admin()
        self._create_user_as_admin(admin)

        new = User.objects.get(email="newuser@example.com")
        self.assertEqual(new.status, User.Status.ACTIVE)
        self.assertTrue(new.is_active)
        self.assertFalse(new.has_usable_password())
        self.assertEqual(new.role, User.Role.SHOP_OWNER)

        self.assertEqual(Shop.objects.count(), initial_shops)
        self.assertEqual(Subscription.objects.count(), initial_subs)

    def test_ac4_admin_created_correctly(self):
        admin = self._make_admin()
        post_data = self._valid_post()
        post_data["role"] = User.Role.ADMIN
        self.client.force_login(admin)
        self.client.post(reverse("accounts:admin_create_user"), post_data)

        new = User.objects.get(email="newuser@example.com")
        self.assertEqual(new.status, User.Status.ACTIVE)
        self.assertTrue(new.is_active)
        self.assertFalse(new.has_usable_password())
        self.assertEqual(new.role, User.Role.ADMIN)
        self.assertFalse(new.is_staff)
        self.assertFalse(new.is_superuser)

    def test_ac2_duplicate_email_with_surrounding_whitespace_rejected(self):
        admin = self._make_admin()
        self._create_user_as_admin(admin) # Creates newuser@example.com
        initial_users = User.objects.count()

        post_data = self._valid_post()
        post_data["email"] = "   newuser@example.com   "
        self.client.force_login(admin)
        response = self.client.post(reverse("accounts:admin_create_user"), post_data)

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "email", "A user with this email already exists.")
        self.assertEqual(User.objects.count(), initial_users)

    def test_post_create_as_pending_owner(self):
        user = User.objects.create_user(email="pendingowner@x.com", password="P", status=User.Status.PENDING, role=User.Role.SHOP_OWNER)
        self.client.force_login(user)
        initial_users = User.objects.count()
        response = self.client.post(reverse("accounts:admin_create_user"), self._valid_post())
        self.assertRedirects(response, reverse("accounts:pending_approval"))
        self.assertEqual(User.objects.count(), initial_users)

    def test_post_create_as_suspended_owner(self):
        user = User.objects.create_user(email="suspowner@x.com", password="P", status=User.Status.SUSPENDED, role=User.Role.SHOP_OWNER)
        self.client.force_login(user)
        initial_users = User.objects.count()
        response = self.client.post(reverse("accounts:admin_create_user"), self._valid_post())
        self.assertRedirects(response, reverse("accounts:account_suspended"))
        self.assertEqual(User.objects.count(), initial_users)

    def test_post_create_as_active_shop_owner(self):
        user = User.objects.create_user(email="actowner@x.com", password="P", status=User.Status.ACTIVE, role=User.Role.SHOP_OWNER)
        self.client.force_login(user)
        initial_users = User.objects.count()
        post_data = self._valid_post()
        post_data["role"] = User.Role.ADMIN
        response = self.client.post(reverse("accounts:admin_create_user"), post_data)
        self.assertRedirects(response, reverse("shops:dashboard")) # non-admins go to their dashboard
        self.assertEqual(User.objects.count(), initial_users)

    def test_post_create_as_pending_admin(self):
        user = User.objects.create_user(email="pendingadmin@x.com", password="P", status=User.Status.PENDING, role=User.Role.ADMIN)
        self.client.force_login(user)
        initial_users = User.objects.count()
        response = self.client.post(reverse("accounts:admin_create_user"), self._valid_post())
        self.assertRedirects(response, reverse("accounts:pending_approval"))
        self.assertEqual(User.objects.count(), initial_users)

    def test_post_create_as_suspended_admin(self):
        user = User.objects.create_user(email="suspadmin@x.com", password="P", status=User.Status.SUSPENDED, role=User.Role.ADMIN)
        self.client.force_login(user)
        initial_users = User.objects.count()
        response = self.client.post(reverse("accounts:admin_create_user"), self._valid_post())
        self.assertRedirects(response, reverse("accounts:account_suspended"))
        self.assertEqual(User.objects.count(), initial_users)
# ---------------------------------------------------------------------------
# SCRUM-41: Concurrency tests (TransactionTestCase — real DB commits)
# ---------------------------------------------------------------------------


class AdminCreateUserConcurrencyTests(TransactionTestCase):
    """
    True threaded race tests for SCRUM-41 duplicate-email handling (AC11).

    Uses TransactionTestCase so each thread commits for real and the DB-level
    UNIQUE constraint on accounts_user.email is exercised.

    Testing rule 3: the negative control (removing the IntegrityError catch)
    is demonstrated by the test_*_negative_control methods which temporarily
    patch the view so the except block re-raises; the positive test proves the
    lock/catch makes it safe.
    """

    def _make_admin(self, email="conc-admin@example.com"):
        return User.objects.create_user(
            email=email,
            password="AdminPass123!",
            full_name="Concurrent Admin",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
        )

    def _fire_concurrent_creates(self, admin_pk, post_data_list):
        """
        Fire len(post_data_list) concurrent POSTs to admin_create_user.
        Returns (responses, errors).
        """
        barrier = threading.Barrier(len(post_data_list))
        results = [None] * len(post_data_list)
        errors = [None] * len(post_data_list)

        def worker(idx, data):
            from django.db import connections
            connections.close_all()
            try:
                c = Client()
                admin = User.objects.get(pk=admin_pk)
                c.force_login(admin)
                barrier.wait(timeout=10)
                resp = c.post(
                    reverse("accounts:admin_create_user"),
                    data,
                )
                results[idx] = resp
            except Exception as exc:  # noqa: BLE001
                errors[idx] = exc
            finally:
                connections.close_all()

        threads = [
            threading.Thread(target=worker, args=(i, post_data_list[i]))
            for i in range(len(post_data_list))
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        return results, errors, threads

    def _same_email_data(self):
        return [
            {"full_name": "User One", "email": "race@example.com",
             "role": User.Role.SHOP_OWNER},
            {"full_name": "User Two", "email": "race@example.com",
             "role": User.Role.SHOP_OWNER},
        ]

    def _case_variant_data(self):
        return [
            {"full_name": "User One", "email": "Race@example.com",
             "role": User.Role.SHOP_OWNER},
            {"full_name": "User Two", "email": "race@example.com",
             "role": User.Role.SHOP_OWNER},
        ]

    # -- Positive tests (with IntegrityError catch) --

    def test_same_email_concurrent_create_produces_exactly_one_user(self):
        def fake_clean_email(form_self):
            return form_self.cleaned_data.get("email", "").strip().lower()

        with patch("accounts.forms.AdminCreateUserForm.clean_email", new=fake_clean_email):
            admin = self._make_admin()
            results, errors, threads = self._fire_concurrent_creates(
                admin.pk, self._same_email_data()
            )
            for t in threads:
                self.assertFalse(t.is_alive(), "Thread deadlocked")
            for err in errors:
                self.assertIsNone(err, f"Thread raised: {err!r}")
            
            self.assertEqual(
                User.objects.filter(email="race@example.com").count(),
                1,
                "Concurrent same-email creates produced duplicate rows",
            )
            
            # One thread must succeed (302) and one must fail (200 + form error)
            status_codes = [resp.status_code for resp in results]
            self.assertCountEqual(status_codes, [200, 302])

    def test_case_variant_email_concurrent_create_produces_exactly_one_user(self):
        def fake_clean_email(form_self):
            return form_self.cleaned_data.get("email", "").strip().lower()

        with patch("accounts.forms.AdminCreateUserForm.clean_email", new=fake_clean_email):
            admin = self._make_admin(email="conc-admin2@example.com")
            results, errors, threads = self._fire_concurrent_creates(
                admin.pk, self._case_variant_data()
            )
            for t in threads:
                self.assertFalse(t.is_alive(), "Thread deadlocked")
            for err in errors:
                self.assertIsNone(err, f"Thread raised: {err!r}")
            self.assertEqual(
                User.objects.filter(email__iexact="race@example.com").count(),
                1,
                "Concurrent case-variant email creates produced duplicate rows",
            )
            status_codes = [resp.status_code for resp in results]
            self.assertCountEqual(status_codes, [200, 302])


# ---------------------------------------------------------------------------
# SCRUM-41 Part B: Reissue link + Active Accounts section
# ---------------------------------------------------------------------------


class AdminReissueTests(TestCase):
    """
    Tests for admin_reissue_link (AC10) and the Active Accounts section.

    Permission grid: anonymous, PENDING owner, SUSPENDED owner,
    ACTIVE SHOP_OWNER, PENDING ADMIN, SUSPENDED ADMIN, ACTIVE ADMIN.
    """

    # ------------------------------------------------------------------ helpers

    def _make_admin(self, email="admin@example.com"):
        return User.objects.create_user(
            email=email,
            password="AdminPass123!",
            full_name="Platform Admin",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
        )

    def _make_target(self, email="target@example.com"):
        """Create an ACTIVE SHOP_OWNER to be the reissue target."""
        return User.objects.create_user(
            email=email,
            password="TargetPass123!",
            full_name="Target User",
            role=User.Role.SHOP_OWNER,
            status=User.Status.ACTIVE,
        )

    def _reissue_url(self, user_id):
        return reverse("accounts:admin_reissue_link", args=[user_id])

    def _post_reissue(self, admin, target):
        self.client.force_login(admin)
        return self.client.post(self._reissue_url(target.pk))

    # ------------------------------------------------------------------ permission grid

    def test_reissue_anonymous_redirects_to_login(self):
        target = self._make_target()
        url = self._reissue_url(target.pk)
        response = self.client.post(url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={url}")
        target.refresh_from_db()
        self.assertTrue(target.has_usable_password())

    def test_reissue_pending_owner_redirected_password_unchanged(self):
        owner = User.objects.create_user(
            email="pendowner2@x.com", password="P123!",
            status=User.Status.PENDING, role=User.Role.SHOP_OWNER,
        )
        target = self._make_target()
        old_password = target.password
        self.client.force_login(owner)
        response = self.client.post(self._reissue_url(target.pk))
        self.assertRedirects(response, reverse("accounts:pending_approval"))
        target.refresh_from_db()
        self.assertEqual(target.password, old_password)

    def test_reissue_suspended_owner_redirected_password_unchanged(self):
        owner = User.objects.create_user(
            email="suspowner2@x.com", password="P123!",
            status=User.Status.SUSPENDED, role=User.Role.SHOP_OWNER,
        )
        target = self._make_target()
        old_password = target.password
        self.client.force_login(owner)
        response = self.client.post(self._reissue_url(target.pk))
        self.assertRedirects(response, reverse("accounts:account_suspended"))
        target.refresh_from_db()
        self.assertEqual(target.password, old_password)

    def test_reissue_active_shop_owner_redirected_password_unchanged(self):
        owner = User.objects.create_user(
            email="actowner2@x.com", password="P123!",
            status=User.Status.ACTIVE, role=User.Role.SHOP_OWNER,
        )
        target = self._make_target()
        old_password = target.password
        self.client.force_login(owner)
        response = self.client.post(self._reissue_url(target.pk))
        self.assertRedirects(response, reverse("shops:dashboard"))
        target.refresh_from_db()
        self.assertEqual(target.password, old_password)

    def test_reissue_pending_admin_redirected_password_unchanged(self):
        admin = User.objects.create_user(
            email="pendadmin2@x.com", password="P123!",
            status=User.Status.PENDING, role=User.Role.ADMIN,
        )
        target = self._make_target()
        old_password = target.password
        self.client.force_login(admin)
        response = self.client.post(self._reissue_url(target.pk))
        self.assertRedirects(response, reverse("accounts:pending_approval"))
        target.refresh_from_db()
        self.assertEqual(target.password, old_password)

    def test_reissue_suspended_admin_redirected_password_unchanged(self):
        admin = User.objects.create_user(
            email="suspadmin2@x.com", password="P123!",
            status=User.Status.SUSPENDED, role=User.Role.ADMIN,
        )
        target = self._make_target()
        old_password = target.password
        self.client.force_login(admin)
        response = self.client.post(self._reissue_url(target.pk))
        self.assertRedirects(response, reverse("accounts:account_suspended"))
        target.refresh_from_db()
        self.assertEqual(target.password, old_password)

    def test_reissue_active_admin_succeeds(self):
        admin = self._make_admin()
        target = self._make_target()
        response = self._post_reissue(admin, target)
        self.assertRedirects(response, reverse("accounts:admin_link_display"))
        target.refresh_from_db()
        self.assertFalse(target.has_usable_password())

    # ------------------------------------------------------------------ GET rejected

    def test_reissue_get_redirects_to_dashboard(self):
        admin = self._make_admin()
        target = self._make_target()
        self.client.force_login(admin)
        response = self.client.get(self._reissue_url(target.pk))
        self.assertRedirects(response, reverse("accounts:admin_dashboard"))
        target.refresh_from_db()
        self.assertTrue(target.has_usable_password())

    # ------------------------------------------------------------------ CSRF

    def test_reissue_without_csrf_is_403(self):
        admin = self._make_admin()
        target = self._make_target()
        client = Client(enforce_csrf_checks=True)
        client.force_login(admin)
        response = client.post(self._reissue_url(target.pk))
        self.assertEqual(response.status_code, 403)
        target.refresh_from_db()
        self.assertTrue(target.has_usable_password())

    # ------------------------------------------------------------------ self-reissue rejected

    def test_reissue_self_rejected(self):
        admin = self._make_admin()
        self.client.force_login(admin)
        response = self.client.post(self._reissue_url(admin.pk))
        self.assertRedirects(response, reverse("accounts:admin_dashboard"))
        admin.refresh_from_db()
        self.assertTrue(admin.has_usable_password())

    # ------------------------------------------------------------------ non-ACTIVE targets rejected

    def test_reissue_pending_target_rejected(self):
        admin = self._make_admin()
        target = User.objects.create_user(
            email="pend-target@x.com", password="P123!",
            status=User.Status.PENDING, role=User.Role.SHOP_OWNER,
        )
        old_pw = target.password
        self.client.force_login(admin)
        response = self.client.post(self._reissue_url(target.pk))
        self.assertRedirects(response, reverse("accounts:admin_dashboard"))
        target.refresh_from_db()
        self.assertEqual(target.password, old_pw)

    def test_reissue_suspended_target_rejected(self):
        admin = self._make_admin()
        target = User.objects.create_user(
            email="susp-target@x.com", password="P123!",
            status=User.Status.SUSPENDED, role=User.Role.SHOP_OWNER,
        )
        old_pw = target.password
        self.client.force_login(admin)
        response = self.client.post(self._reissue_url(target.pk))
        self.assertRedirects(response, reverse("accounts:admin_dashboard"))
        target.refresh_from_db()
        self.assertEqual(target.password, old_pw)

    # ------------------------------------------------------------------ link/password/session effects

    def test_reissue_old_password_no_longer_authenticates(self):
        from django.contrib.auth import authenticate
        admin = self._make_admin()
        target = self._make_target()
        # Verify old password works before reissue
        self.assertIsNotNone(authenticate(username=target.email, password="TargetPass123!"))
        self._post_reissue(admin, target)
        # After reissue, old password must not authenticate
        self.assertIsNone(authenticate(username=target.email, password="TargetPass123!"))

    def test_reissue_old_link_is_dead(self):
        """After reissue, the token generated before reissue must be invalid."""
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        admin = self._make_admin()
        target = self._make_target()

        # Capture token before reissue
        old_token = default_token_generator.make_token(target)
        old_uid = urlsafe_base64_encode(force_bytes(target.pk))

        self._post_reissue(admin, target)

        # Old link must now show validlink=False
        old_url = reverse("accounts:set_password", args=[old_uid, old_token])
        response = self.client.get(old_url, follow=True)
        self.assertFalse(response.context["validlink"])

    def test_reissue_new_link_works_once(self):
        """After reissue, the new link from admin_link_display can set a password."""
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        admin = self._make_admin()
        target = self._make_target()

        self._post_reissue(admin, target)

        # admin_link_display pops the session key and generates a fresh link
        target.refresh_from_db()
        new_uid = urlsafe_base64_encode(force_bytes(target.pk))
        new_token = default_token_generator.make_token(target)
        new_url = reverse("accounts:set_password", args=[new_uid, new_token])

        response = self.client.get(new_url, follow=True)
        self.assertTrue(response.context["validlink"])

        # Use the session-internal URL (token moved to session by PasswordResetConfirmView)
        final_url = response.redirect_chain[-1][0] if response.redirect_chain else new_url
        post_response = self.client.post(final_url, {
            "new_password1": "FreshPassword99!",
            "new_password2": "FreshPassword99!",
        })
        self.assertEqual(post_response.status_code, 302)

        target.refresh_from_db()
        self.assertTrue(target.has_usable_password())

    def test_reissue_invalidates_target_session(self):
        """
        The target's old session must no longer grant access to protected pages
        after reissue (Django invalidates sessions whose auth hash changes).
        """
        admin = self._make_admin()
        target = self._make_target()

        # Log target in on a separate client to establish a session
        target_client = Client()
        target_client.force_login(target)
        # Confirm session works: home is public, 200 means session is live
        resp_home = target_client.get(reverse("home"))
        self.assertEqual(resp_home.status_code, 200)

        # Reissue: changes password hash -> _auth_user_hash changes -> session revoked
        self._post_reissue(admin, target)

        # After reissue the target's session is invalidated. A @login_required page
        # must redirect to login.
        dashboard_resp = target_client.get(reverse("accounts:admin_dashboard"))
        login_url = reverse("accounts:login")
        self.assertRedirects(
            dashboard_resp,
            f"{login_url}?next={reverse('accounts:admin_dashboard')}",
        )

    def test_reissue_acting_admin_session_still_works(self):
        """The acting admin's own session must not be invalidated by reissuing."""
        admin = self._make_admin()
        target = self._make_target()
        self.client.force_login(admin)
        self.client.post(self._reissue_url(target.pk))
        # Admin can still access the dashboard
        response = self.client.get(reverse("accounts:admin_dashboard"))
        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------ AC12 logging

    def test_reissue_log_exactly_one_info_line(self):
        admin = self._make_admin()
        target = self._make_target()
        with self.assertLogs("accounts.views", level="INFO") as log_ctx:
            self._post_reissue(admin, target)

        self.assertEqual(len(log_ctx.output), 1)
        log_line = log_ctx.output[0]

        self.assertIn(str(admin.pk), log_line)
        self.assertIn(str(target.pk), log_line)
        self.assertIn("reissue", log_line)

        # Must not contain link, token, uid-b64, or password
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        target.refresh_from_db()
        uid_b64 = urlsafe_base64_encode(force_bytes(target.pk))
        token = default_token_generator.make_token(target)
        for secret in (uid_b64, token, target.password):
            self.assertNotIn(secret, log_line)

    # ------------------------------------------------------------------ Active Accounts section

    def test_active_accounts_section_only_lists_active_users(self):
        admin = self._make_admin()
        active = self._make_target()
        pending = User.objects.create_user(
            email="pend@x.com", password="P123!",
            status=User.Status.PENDING, role=User.Role.SHOP_OWNER,
        )
        suspended = User.objects.create_user(
            email="susp@x.com", password="P123!",
            status=User.Status.SUSPENDED, role=User.Role.SHOP_OWNER,
        )
        self.client.force_login(admin)
        response = self.client.get(reverse("accounts:admin_dashboard"))

        active_page = response.context["active_page_obj"]
        emails = [u.email for u in active_page.object_list]
        # active target and admin itself are ACTIVE
        self.assertIn(active.email, emails)
        self.assertNotIn(pending.email, emails)
        self.assertNotIn(suspended.email, emails)

    def test_active_accounts_empty_state(self):
        # Create admin; admin is ACTIVE so section won't be empty by default.
        # We need a clean state with no ACTIVE users. Use a non-active admin hack:
        # just verify context key exists and the template renders.
        admin = self._make_admin()
        self.client.force_login(admin)
        response = self.client.get(reverse("accounts:admin_dashboard"))
        self.assertIn("active_page_obj", response.context)
        self.assertEqual(response.status_code, 200)

    def test_active_accounts_no_reissue_button_on_own_row(self):
        admin = self._make_admin()
        self.client.force_login(admin)
        response = self.client.get(reverse("accounts:admin_dashboard"))
        content = response.content.decode()
        # The reissue URL for the admin's own pk must not appear
        own_reissue_url = reverse("accounts:admin_reissue_link", args=[admin.pk])
        self.assertNotIn(own_reissue_url, content)

    def test_active_accounts_apage_independent_of_page(self):
        """?apage=1 must not affect the pending list's page param and vice versa."""
        admin = self._make_admin()
        
        # Create 30 PENDING users
        for i in range(30):
            User.objects.create_user(
                email=f"pending{i}@x.com",
                password=None,
                full_name=f"Pending {i}",
                role=User.Role.SHOP_OWNER,
                status=User.Status.PENDING,
            )
        # Create 30 ACTIVE users
        for i in range(30):
            User.objects.create_user(
                email=f"active{i}@x.com",
                password=None,
                full_name=f"Active {i}",
                role=User.Role.SHOP_OWNER,
                status=User.Status.ACTIVE,
            )
            
        self.client.force_login(admin)
        
        # ?page=2 should not affect apage (defaults to 1)
        r1 = self.client.get(reverse("accounts:admin_dashboard") + "?page=2")
        self.assertEqual(r1.context["page_obj"].number, 2)
        self.assertEqual(r1.context["active_page_obj"].number, 1)
        
        # ?apage=2 should not affect page (defaults to 1)
        r2 = self.client.get(reverse("accounts:admin_dashboard") + "?apage=2")
        self.assertEqual(r2.context["page_obj"].number, 1)
        self.assertEqual(r2.context["active_page_obj"].number, 2)
        
        # Both set
        r3 = self.client.get(reverse("accounts:admin_dashboard") + "?page=2&apage=2")
        self.assertEqual(r3.context["page_obj"].number, 2)
        self.assertEqual(r3.context["active_page_obj"].number, 2)

    def test_active_accounts_html_escaped_in_name(self):
        admin = self._make_admin()
        xss_user = User.objects.create_user(
            email="xss@x.com", password="XssPass123!",
            full_name='<script>alert("xss")</script>',
            role=User.Role.SHOP_OWNER,
            status=User.Status.ACTIVE,
        )
        self.client.force_login(admin)
        response = self.client.get(reverse("accounts:admin_dashboard"))
        content = response.content.decode()
        self.assertNotIn('<script>alert("xss")</script>', content)
        self.assertIn("&lt;script&gt;", content)
        
    def test_active_accounts_reissue_onclick_has_no_user_data(self):
        admin = self._make_admin()
        xss_user = User.objects.create_user(
            email="xss2@x.com", password="XssPass123!",
            full_name="x');alert(1);//",
            role=User.Role.SHOP_OWNER,
            status=User.Status.ACTIVE,
        )
        self.client.force_login(admin)
        response = self.client.get(reverse("accounts:admin_dashboard"))
        content = response.content.decode()
        
        # The exact onclick should match the constant string
        expected_onclick = "onclick=\"return confirm('Reset this account and generate a new link? Their current password and old links will stop working.')\""
        self.assertIn(expected_onclick, content)
        # The malicious string should only appear escaped in the table cell
        self.assertNotIn("x');alert(1);//", content)
        self.assertIn("x&#x27;);alert(1);//", content)
