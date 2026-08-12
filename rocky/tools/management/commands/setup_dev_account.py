import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ObjectDoesNotExist
from django.core.management import BaseCommand

from tools.models import GROUP_ADMIN, GROUP_CLIENT, GROUP_REDTEAM

User = get_user_model()


class Command(BaseCommand):
    help = "Creates the development organization, member, groups and set permissions."

    def get_permissions(self, codenames):
        permission_objects = []
        if codenames:
            for codename in codenames:
                try:
                    permission = Permission.objects.get(codename=codename)
                except Permission.DoesNotExist:
                    raise ObjectDoesNotExist("Permission:" + codename + " does not exist.")
                else:
                    permission_objects.append(permission.id)

        return permission_objects

    def setup_kat_groups(self):
        self.group_admin, self.group_admin_created = Group.objects.get_or_create(name=GROUP_ADMIN)

        self.group_redteam, self.group_redteam_created = Group.objects.get_or_create(name=GROUP_REDTEAM)

        self.group_client, self.group_client_created = Group.objects.get_or_create(name=GROUP_CLIENT)

    def handle(self, *args, **options):
        self.setup_kat_groups()

        redteamer_permissions = [
            "can_scan_organization",
            "can_enable_disable_boefje",
            "can_add_boefje",
            "can_set_clearance_level",
            "can_delete_oois",
            "can_mute_findings",
            "can_view_katalogus_settings",
            "can_set_katalogus_settings",
        ]

        redteam_permissions = self.get_permissions(redteamer_permissions)
        self.group_redteam.permissions.set(redteam_permissions)

        admin_permissions = self.get_permissions(
            redteamer_permissions
            + [
                "view_organization",
                "view_organizationmember",
                "add_organizationmember",
                "change_organization",
                "can_scan_organization",
                "change_organizationmember",
                "add_indemnification",
                "can_recalculate_bits",
            ]
        )
        self.group_admin.permissions.set(admin_permissions)

        client_permissions = self.get_permissions(["can_scan_organization"])
        self.group_client.permissions.set(client_permissions)

        logging.info("ROCKY HAS BEEN SETUP SUCCESSFULLY")
