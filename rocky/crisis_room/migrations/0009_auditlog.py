import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("crisis_room", "0008_alter_dashboard_organization"),
        ("tools", "0047_alter_organization_code_alter_organization_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("actor_label", models.CharField(max_length=254)),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("indemnification_set", "Set indemnification"),
                            ("object_added", "Added object"),
                            ("object_updated", "Updated object"),
                            ("object_deleted", "Deleted object"),
                            ("clearance_level_changed", "Changed clearance level"),
                            ("plugin_enabled", "Enabled plugin"),
                            ("plugin_disabled", "Disabled plugin"),
                            ("plugin_settings_changed", "Changed plugin settings"),
                            ("plugin_settings_deleted", "Deleted plugin settings"),
                        ],
                        max_length=32,
                    ),
                ),
                ("object_type", models.CharField(blank=True, max_length=64)),
                ("object_label", models.TextField(blank=True, default="")),
                ("object_pk", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "actor",
                    models.ForeignKey(
                        null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="audit_logs", to="tools.organization"
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["organization", "-created_at"], name="audit_log_org_created_idx")
                ],
            },
        )
    ]
