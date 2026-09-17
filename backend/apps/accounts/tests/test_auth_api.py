from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.core.tests.factories import create_operator_account


class AuthenticationApiTests(APITestCase):
    def setUp(self):
        self.user, self.operator, _, _ = create_operator_account("auth")

    def login(self):
        return self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "a-secure-password"},
            format="json",
        )

    def test_login_and_me_include_authenticated_operator(self):
        response = self.login()

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["operator"]["id"], str(self.operator.id))

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        me = self.client.get("/api/v1/auth/me/")

        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["user"]["email"], self.user.email)
        self.assertEqual(me.data["operator"]["id"], str(self.operator.id))

    def test_user_without_operator_cannot_login(self):
        user = get_user_model().objects.create_user(
            "alone@example.com", "a-secure-password"
        )

        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "a-secure-password"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"]["code"], "OPERATOR_INACTIVE")

    def test_refresh_rotates_and_logout_revokes_token(self):
        login = self.login()
        old_refresh = login.data["refresh"]

        rotated = self.client.post(
            "/api/v1/auth/refresh/", {"refresh": old_refresh}, format="json"
        )
        self.assertEqual(rotated.status_code, 200)
        self.assertIn("refresh", rotated.data)

        reused = self.client.post(
            "/api/v1/auth/refresh/", {"refresh": old_refresh}, format="json"
        )
        self.assertEqual(reused.status_code, 401)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {rotated.data['access']}")
        logout = self.client.post(
            "/api/v1/auth/logout/",
            {"refresh": rotated.data["refresh"]},
            format="json",
        )
        self.assertEqual(logout.status_code, 204)

        after_logout = self.client.post(
            "/api/v1/auth/refresh/",
            {"refresh": rotated.data["refresh"]},
            format="json",
        )
        self.assertEqual(after_logout.status_code, 401)

    def test_deactivated_operator_blocks_existing_access_token(self):
        login = self.login()
        self.operator.is_active = False
        self.operator.save(update_fields=("is_active",))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        response = self.client.get("/api/v1/auth/me/")

        self.assertEqual(response.status_code, 401)

