from datetime import datetime
from typing import Protocol

from django.db import transaction

from apps.operators.models import Operator

from .models import Plan, Subscription


class SubscriptionProvider(Protocol):
    def assign(
        self,
        *,
        operator: Operator,
        plan: Plan,
        starts_at: datetime,
        expires_at: datetime,
        status: str,
    ) -> Subscription: ...


class ManualSubscriptionProvider:
    @transaction.atomic
    def assign(
        self,
        *,
        operator: Operator,
        plan: Plan,
        starts_at: datetime,
        expires_at: datetime,
        status: str = Subscription.Status.ACTIVE,
    ) -> Subscription:
        locked_operator = Operator.objects.select_for_update().get(pk=operator.pk)
        Subscription.objects.filter(
            operator=locked_operator, is_current=True
        ).update(is_current=False)
        subscription = Subscription(
            operator=locked_operator,
            plan=plan,
            starts_at=starts_at,
            expires_at=expires_at,
            status=status,
            provider=Subscription.Provider.MANUAL,
            is_current=True,
        )
        subscription.full_clean()
        subscription.save()
        return subscription

