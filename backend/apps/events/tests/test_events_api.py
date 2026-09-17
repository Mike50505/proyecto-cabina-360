from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.core.tests.factories import create_operator_account
from apps.events.models import Event, EventType


def event_payload(event_type, **overrides):
    payload = {
        "name": "Boda Ana y Carlos",
        "description": "Nuestro evento de prueba",
        "event_type": str(event_type.id),
        "event_date": (timezone.now() + timedelta(days=7)).isoformat(),
        "token_pool_size": 3,
        "settings": {
            "resolution": "1080p",
            "camera_id": "back-main",
            "bitrate_mode": "AUTOMATIC",
            "duration_seconds": 8,
            "countdown_seconds": 3,
            "orientation": "PORTRAIT",
        },
    }
    payload.update(overrides)
    return payload


class EventApiTests(APITestCase):
    def setUp(self):
        self.user, self.operator, self.plan, self.subscription = create_operator_account(
            "events"
        )
        self.event_type = EventType.objects.get(code="wedding")
        self.client.force_authenticate(self.user)

    def create_event(self, **overrides):
        return self.client.post(
            "/api/v1/events/",
            event_payload(self.event_type, **overrides),
            format="json",
        )

    def test_create_event_reserves_public_video_tokens(self):
        response = self.create_event()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Event.Status.DRAFT)
        self.assertEqual(len(response.data["reserved_video_tokens"]), 3)
        self.assertTrue(response.data["public_url"].startswith("http://localhost/e/"))
        self.assertEqual(Event.objects.get().operator, self.operator)

    def test_other_operator_event_returns_not_found(self):
        event_id = self.create_event().data["id"]
        other_user, _, _, _ = create_operator_account("events-other")
        self.client.force_authenticate(other_user)

        response = self.client.get(f"/api/v1/events/{event_id}/")

        self.assertEqual(response.status_code, 404)

    def test_deleted_event_still_counts_toward_monthly_limit(self):
        self.plan.max_events_per_month = 1
        self.plan.save(update_fields=("max_events_per_month",))
        first = self.create_event()
        deleted = self.client.delete(f"/api/v1/events/{first.data['id']}/")

        second = self.create_event(name="Segundo evento")

        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(second.data["error"]["code"], "EVENT_LIMIT_REACHED")
        self.assertEqual(Event.objects.count(), 1)

    def test_start_and_finish_are_idempotent(self):
        event_id = self.create_event().data["id"]
        first_start = self.client.post(f"/api/v1/events/{event_id}/start/")
        second_start = self.client.post(f"/api/v1/events/{event_id}/start/")

        self.subscription.expires_at = timezone.now() - timedelta(seconds=1)
        self.subscription.save(update_fields=("expires_at",))
        first_finish = self.client.post(f"/api/v1/events/{event_id}/finish/")
        second_finish = self.client.post(f"/api/v1/events/{event_id}/finish/")

        self.assertEqual(first_start.status_code, 200)
        self.assertEqual(second_start.status_code, 200)
        self.assertEqual(first_finish.status_code, 200)
        self.assertEqual(second_finish.status_code, 200)
        self.assertEqual(first_finish.data["status"], Event.Status.FINISHED)
        self.assertIsNotNone(first_finish.data["retention_until"])

    def test_invalid_state_transition_returns_consistent_error(self):
        event_id = self.create_event().data["id"]

        response = self.client.post(f"/api/v1/events/{event_id}/finish/")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "INVALID_EVENT_TRANSITION")

    def test_reserve_more_tokens(self):
        event_id = self.create_event().data["id"]

        response = self.client.post(
            f"/api/v1/events/{event_id}/video-tokens/reserve/",
            {"quantity": 2},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(Event.objects.get().video_tokens.count(), 5)

    def test_advanced_bitrate_requires_value(self):
        payload = event_payload(self.event_type)
        payload["settings"]["bitrate_mode"] = "ADVANCED"

        response = self.client.post("/api/v1/events/", payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Event.objects.count(), 0)
