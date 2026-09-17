from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.core.tests.factories import create_operator_account
from apps.subscriptions.models import Subscription
from apps.subscriptions.providers import ManualSubscriptionProvider


class SubscriptionApiTests(APITestCase):
    def test_returns_only_authenticated_operator_subscription(self):
        user_a, operator_a, plan_a, _ = create_operator_account("subscription-a")
        _, _, plan_b, _ = create_operator_account("subscription-b")
        self.client.force_authenticate(user_a)

        response = self.client.get("/api/v1/subscription/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["plan"]["code"], plan_a.code)
        self.assertNotEqual(response.data["plan"]["code"], plan_b.code)
        self.assertTrue(response.data["grants_access"])

    def test_expired_subscription_is_reported_without_access(self):
        user, _, _, subscription = create_operator_account("expired")
        subscription.expires_at = timezone.now() - timedelta(seconds=1)
        subscription.save(update_fields=("expires_at",))
        self.client.force_authenticate(user)

        response = self.client.get("/api/v1/subscription/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["grants_access"])

    def test_inactive_plan_does_not_grant_access(self):
        user, _, plan, _ = create_operator_account("inactive-plan")
        plan.is_active = False
        plan.save(update_fields=("is_active",))
        self.client.force_authenticate(user)

        response = self.client.get("/api/v1/subscription/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["grants_access"])

    def test_manual_provider_replaces_current_subscription(self):
        _, operator, plan, previous = create_operator_account("manual-provider")

        replacement = ManualSubscriptionProvider().assign(
            operator=operator,
            plan=plan,
            starts_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=60),
        )

        previous.refresh_from_db()
        self.assertFalse(previous.is_current)
        self.assertTrue(replacement.is_current)
        self.assertEqual(
            Subscription.objects.filter(operator=operator, is_current=True).count(), 1
        )
