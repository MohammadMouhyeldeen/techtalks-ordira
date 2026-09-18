import threading

from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

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