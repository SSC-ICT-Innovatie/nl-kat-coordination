from django.contrib.auth.management import create_permissions
from django.db import migrations

from tools.models import GROUP_ADMIN, GROUP_REDTEAM


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
        admin.permissions.add(Permission.objects.get(codename="can_enable_disable_schedule"))

        redteam = Group.objects.get(name=GROUP_REDTEAM)
        redteam.permissions.add(Permission.objects.get(codename="can_enable_disable_schedule"))
    except Group.DoesNotExist:
        pass


class Migration(migrations.Migration):
    dependencies = [("tools", "0045_alter_organization_options")]

    operations = [migrations.RunPython(migrate_permissions), migrations.RunPython(add_group_permissions)]
