from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import override_settings
from rest_framework.test import APITestCase


class HealthViewTests(APITestCase):
    def test_health_reports_database_and_storage(self):
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=Path(directory)):
            response = self.client.get("/api/v1/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "checks": {"database": True, "storage": True}},
        )

