from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.core.tests.factories import create_operator_account
from apps.events.models import Event, EventType, ReservedVideoToken


class PublicGalleryTests(TestCase):
    def setUp(self):
        _, operator, _, _ = create_operator_account("public")
        event_type = EventType.objects.get(code="party")
        self.event = Event.objects.create(
            operator=operator,
            event_type=event_type,
            name="Fiesta pública",
            event_date=timezone.now(),
            status=Event.Status.ACTIVE,
            settings={},
        )
        self.token = ReservedVideoToken.objects.create(event=self.event)

    def test_event_page_is_available_without_account(self):
        response = self.client.get(f"/e/{self.event.public_token}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fiesta pública")

    def test_reserved_video_token_shows_pending_page(self):
        response = self.client.get(f"/v/{self.token.public_token}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tu video se está preparando")

    def test_disabled_or_expired_event_returns_gone(self):
        self.event.retention_until = timezone.now() - timedelta(seconds=1)
        self.event.save(update_fields=("retention_until",))

        event_response = self.client.get(f"/e/{self.event.public_token}/")
        video_response = self.client.get(f"/v/{self.token.public_token}/")

        self.assertEqual(event_response.status_code, 410)
        self.assertEqual(video_response.status_code, 410)

    def test_unknown_token_does_not_reveal_an_event(self):
        response = self.client.get("/e/not-a-real-token/")

        self.assertEqual(response.status_code, 404)
