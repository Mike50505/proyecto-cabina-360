from django.db import migrations


INITIAL_EVENT_TYPES = (
    ("wedding", "Boda", "favorite", 10),
    ("quinceanera", "XV años", "celebration", 20),
    ("birthday", "Cumpleaños", "cake", 30),
    ("graduation", "Graduación", "school", 40),
    ("corporate", "Evento empresarial", "business", 50),
    ("party", "Fiesta", "nightlife", 60),
    ("other", "Otro", "more_horiz", 70),
)


def seed_event_types(apps, schema_editor):
    event_type = apps.get_model("events", "EventType")
    for code, name, icon, sort_order in INITIAL_EVENT_TYPES:
        event_type.objects.get_or_create(
            code=code,
            defaults={"name": name, "icon": icon, "sort_order": sort_order},
        )


class Migration(migrations.Migration):
    dependencies = [("events", "0001_initial")]

    operations = [migrations.RunPython(seed_event_types, migrations.RunPython.noop)]

