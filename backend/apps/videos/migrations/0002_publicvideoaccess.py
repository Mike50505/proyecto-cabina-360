import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("videos", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="PublicVideoAccess",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("action", models.CharField(choices=[("VIEW", "Vista"), ("STREAM", "Reproducción"), ("DOWNLOAD", "Descarga")], max_length=12)),
                ("ip_hash", models.CharField(blank=True, max_length=64)),
                ("user_agent", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("video", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="public_accesses", to="videos.video")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddIndex(
            model_name="publicvideoaccess",
            index=models.Index(fields=["video", "action", "created_at"], name="videos_access_lookup_idx"),
        ),
    ]
