from django.contrib.auth.management import create_permissions
from django.db import migrations

from tools.models import GROUP_ADMIN


# same as in 0026_auto_20221031_1344.py
# https://stackoverflow.com/a/40092780/1336275
def migrate_permissions(apps, schema_editor):
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None


def add_group_permissions(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    try:
        admin = Group.objects.get(name=GROUP_ADMIN)

        redteamer_permissions = [
            "can_scan_organization",
            "can_enable_disable_boefje",
            "can_set_clearance_level",
            "can_delete_oois",
            "can_mute_findings",
            "can_view_katalogus_settings",
            "can_set_katalogus_settings",
        ]

        for permission in redteamer_permissions:
            admin.permissions.add(Permission.objects.get(codename=permission))
    except Group.DoesNotExist:
        pass


class Migration(migrations.Migration):
    dependencies = [("tools", "0039_update_permissions")]

    operations = [migrations.RunPython(migrate_permissions), migrations.RunPython(add_group_permissions)]
