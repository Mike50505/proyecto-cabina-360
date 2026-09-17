from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.operators.models import OperatorMembership
from apps.subscriptions.models import Subscription


@override_settings(DEBUG=True)
class SeedDemoCommandTests(TestCase):
    def test_command_is_idempotent_and_creates_a_complete_account(self):
        call_command("seed_demo")
        call_command("seed_demo")

        user = User.objects.get(email="demo@cabina360.local")
        membership = OperatorMembership.objects.get(user=user)
        subscription = Subscription.objects.get(operator=membership.operator, is_current=True)

        self.assertTrue(user.check_password("Cabina360Demo!"))
        self.assertEqual(membership.role, OperatorMembership.Role.OWNER)
        self.assertTrue(subscription.grants_access)
        self.assertEqual(User.objects.filter(email=user.email).count(), 1)
