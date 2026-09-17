from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.operators.models import Operator, OperatorMembership
from apps.subscriptions.models import Plan, Subscription


def create_operator_account(suffix: str = "one", *, max_devices: int = 2):
    user = get_user_model().objects.create_user(
        email=f"operator-{suffix}@example.com",
        password="a-secure-password",
        first_name="Operador",
    )
    operator = Operator.objects.create(name=f"Cabina {suffix}")
    OperatorMembership.objects.create(
        user=user,
        operator=operator,
        role=OperatorMembership.Role.OWNER,
    )
    plan = Plan.objects.create(
        code=f"plan-{suffix}",
        name=f"Plan {suffix}",
        max_devices=max_devices,
    )
    subscription = Subscription.objects.create(
        operator=operator,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        expires_at=timezone.now() + timedelta(days=30),
    )
    return user, operator, plan, subscription

