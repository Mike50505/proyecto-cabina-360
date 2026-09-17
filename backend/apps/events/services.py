from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.operators.models import Operator
from apps.subscriptions.services import current_subscription, require_active_subscription

from .models import Event, ReservedVideoToken

MAX_TOKEN_RESERVATION_BATCH = 100
DEFAULT_TOKEN_POOL_SIZE = 30


def reserve_video_tokens(event: Event, quantity: int) -> list[ReservedVideoToken]:
    if quantity < 1 or quantity > MAX_TOKEN_RESERVATION_BATCH:
        raise ValidationError(
            {"quantity": f"Debe estar entre 1 y {MAX_TOKEN_RESERVATION_BATCH}."},
            code="invalid_token_quantity",
        )
    return ReservedVideoToken.objects.bulk_create(
        [ReservedVideoToken(event=event) for _ in range(quantity)]
    )


@transaction.atomic
def create_event(*, operator: Operator, validated_data: dict, token_pool_size: int) -> Event:
    locked_operator = Operator.objects.select_for_update().get(pk=operator.pk)
    subscription = require_active_subscription(locked_operator)
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    events_this_month = locked_operator.events.filter(created_at__gte=month_start).count()
    if events_this_month >= subscription.plan.max_events_per_month:
        raise ValidationError(
            {"event": "Tu plan alcanzó el límite mensual de eventos."},
            code="event_limit_reached",
        )
    event = Event.objects.create(operator=locked_operator, **validated_data)
    reserve_video_tokens(event, token_pool_size)
    return event


@transaction.atomic
def start_event(event: Event) -> Event:
    event = Event.objects.select_for_update().get(pk=event.pk)
    if event.status == Event.Status.ACTIVE:
        return event
    if event.status != Event.Status.DRAFT:
        raise ValidationError(
            {"status": "Solo un borrador puede iniciarse."}, code="invalid_event_transition"
        )
    require_active_subscription(event.operator)
    event.status = Event.Status.ACTIVE
    event.started_at = timezone.now()
    event.save(update_fields=("status", "started_at", "updated_at"))
    return event


@transaction.atomic
def finish_event(event: Event) -> Event:
    event = Event.objects.select_for_update().get(pk=event.pk)
    if event.status == Event.Status.FINISHED:
        return event
    if event.status != Event.Status.ACTIVE:
        raise ValidationError(
            {"status": "Solo un evento activo puede finalizarse."},
            code="invalid_event_transition",
        )
    subscription = current_subscription(event.operator)
    if subscription is None:
        raise ValidationError(
            {"status": "El evento no tiene una política de retención asociada."},
            code="retention_policy_missing",
        )
    finished_at = timezone.now()
    event.status = Event.Status.FINISHED
    event.finished_at = finished_at
    event.retention_until = finished_at + timedelta(days=subscription.plan.retention_days)
    event.save(
        update_fields=("status", "finished_at", "retention_until", "updated_at")
    )
    return event
