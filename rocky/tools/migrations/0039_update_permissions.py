from django.contrib.auth.management import create_permissions
from django.db import migrations

from tools.models import GROUP_ADMIN, GROUP_CLIENT, GROUP_REDTEAM


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
        admin.permissions.add(Permission.objects.get(codename="can_recalculate_bits"))

        redteam = Group.objects.get(name=GROUP_REDTEAM)
        redteam.permissions.add(Permission.objects.get(codename="can_mute_findings"))
        redteam.permissions.add(Permission.objects.get(codename="can_view_katalogus_settings"))
        redteam.permissions.add(Permission.objects.get(codename="can_set_katalogus_settings"))

        clients = Group.objects.get(name=GROUP_CLIENT)
        clients.permissions.add(Permission.objects.get(codename="can_scan_organization"))
    except Group.DoesNotExist:
        pass


class Migration(migrations.Migration):
    dependencies = [("tools", "0039_merge_0038_alter_organization_options_0038_delete_job")]

    operations = [migrations.RunPython(migrate_permissions), migrations.RunPython(add_group_permissions)]
