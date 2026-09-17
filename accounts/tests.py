from django.test import TestCase
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