from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.operators.models import Operator, OperatorMembership
from apps.subscriptions.models import Plan, Subscription


class Command(BaseCommand):
    help = "Crea o actualiza una cuenta de demostración para probar la app Android."

    def add_arguments(self, parser):
        parser.add_argument("--email", default="demo@cabina360.local")
        parser.add_argument("--password", default="Cabina360Demo!")

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo solo puede ejecutarse con DEBUG=true.")

        email = options["email"].strip().lower()
        password = options["password"]
        if len(password) < 8:
            raise CommandError("La contraseña debe tener al menos 8 caracteres.")

        user, _ = User.objects.get_or_create(
            email=email,
            defaults={"first_name": "Operador", "last_name": "Demo"},
        )
        user.first_name = "Operador"
        user.last_name = "Demo"
        user.is_active = True
        user.set_password(password)
        user.save()

        operator, _ = Operator.objects.get_or_create(
            name="Cabina 360 Demo",
            defaults={"phone": "", "is_active": True},
        )
        operator.is_active = True
        operator.save(update_fields=("is_active", "updated_at"))

        membership, _ = OperatorMembership.objects.get_or_create(
            operator=operator,
            user=user,
            defaults={"role": OperatorMembership.Role.OWNER},
        )
        membership.role = OperatorMembership.Role.OWNER
        membership.is_active = True
        membership.save(update_fields=("role", "is_active"))

        plan, _ = Plan.objects.update_or_create(
            code="demo",
            defaults={
                "name": "Plan Demo",
                "price": 0,
                "currency": "MXN",
                "max_events_per_month": 20,
                "retention_days": 30,
                "max_storage_bytes": 10 * 1024**3,
                "max_devices": 2,
                "branding_enabled": False,
                "features": ["Galería pública", "Carga reanudable"],
                "is_active": True,
            },
        )
        now = timezone.now()
        subscription = Subscription.objects.filter(operator=operator, is_current=True).first()
        if subscription is None:
            subscription = Subscription(operator=operator, is_current=True)
        subscription.plan = plan
        subscription.status = Subscription.Status.TRIAL
        subscription.provider = Subscription.Provider.MANUAL
        subscription.starts_at = now
        subscription.expires_at = now + timedelta(days=30)
        subscription.full_clean()
        subscription.save()

        self.stdout.write(self.style.SUCCESS("Cuenta demo lista."))
        self.stdout.write(f"Correo: {email}")
        self.stdout.write(f"Contraseña: {password}")
