import uuid

from rest_framework.test import APITestCase

from apps.core.tests.factories import create_operator_account
from apps.operators.models import Device


class DeviceApiTests(APITestCase):
    def setUp(self):
        self.user_a, self.operator_a, _, _ = create_operator_account(
            "device-a", max_devices=1
        )
        self.user_b, self.operator_b, _, _ = create_operator_account("device-b")
        self.foreign_installation_id = uuid.uuid4()
        Device.objects.create(
            operator=self.operator_b,
            registered_by=self.user_b,
            installation_id=self.foreign_installation_id,
            name="Teléfono B",
        )
        self.client.force_authenticate(self.user_a)

    def test_list_only_returns_current_operator_devices(self):
        response = self.client.get("/api/v1/devices/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_operator_cannot_claim_another_operator_device(self):
        response = self.client.post(
            "/api/v1/devices/",
            {
                "installation_id": str(self.foreign_installation_id),
                "name": "Intento de reasignación",
                "app_version": "1.0.0",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        device = Device.objects.get(installation_id=self.foreign_installation_id)
        self.assertEqual(device.operator, self.operator_b)

    def test_plan_device_limit_is_enforced(self):
        first = self.client.post(
            "/api/v1/devices/",
            {"installation_id": str(uuid.uuid4()), "name": "Primero"},
            format="json",
        )
        second = self.client.post(
            "/api/v1/devices/",
            {"installation_id": str(uuid.uuid4()), "name": "Segundo"},
            format="json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(self.operator_a.devices.count(), 1)

    def test_registering_same_installation_updates_without_duplicate(self):
        installation_id = uuid.uuid4()
        first = self.client.post(
            "/api/v1/devices/",
            {"installation_id": str(installation_id), "name": "Nombre inicial"},
            format="json",
        )
        second = self.client.post(
            "/api/v1/devices/",
            {
                "installation_id": str(installation_id),
                "name": "Nombre actualizado",
                "app_version": "2.0.0",
            },
            format="json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(self.operator_a.devices.count(), 1)
        self.assertEqual(self.operator_a.devices.get().name, "Nombre actualizado")
