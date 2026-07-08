from django.db import migrations, models


def delete_orphan_dashboards(apps, schema_editor):
    Dashboard = apps.get_model("crisis_room", "Dashboard")
    Dashboard.objects.filter(organization__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("crisis_room", "0007_alter_dashboarditem_source"),
        ("tools", "0047_alter_organization_code_alter_organization_name"),
    ]

    operations = [
        migrations.RunPython(delete_orphan_dashboards, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="dashboard",
            name="organization",
            field=models.ForeignKey(null=True, on_delete=models.CASCADE, to="tools.organization"),
        ),
    ]
