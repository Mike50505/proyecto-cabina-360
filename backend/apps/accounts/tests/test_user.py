from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from django.test import TestCase


class UserManagerTests(TestCase):
    def test_create_user_uses_email_as_identity(self):
        user = get_user_model().objects.create_user("Operator@Example.com", "a-secure-password")

        self.assertEqual(user.email, "Operator@example.com")
        self.assertTrue(user.check_password("a-secure-password"))
        with self.assertRaises(FieldDoesNotExist):
            user._meta.get_field("username")

    def test_create_superuser_can_open_user_admin(self):
        user = get_user_model().objects.create_superuser(
            "admin@example.com", "a-secure-password"
        )
        self.client.force_login(user)

        response = self.client.get("/admin/accounts/user/add/")

        self.assertEqual(response.status_code, 200)
