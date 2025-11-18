import json
import logging
from pathlib import Path

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.core.management import BaseCommand

from objects.models import SEVERITY_SCORE_LOOKUP, FindingType, Hostname, Network, object_type_by_name
from openkat.models import GROUP_ADMIN, GROUP_READ_ONLY, Organization
from plugins.models import BusinessRule, Plugin
from plugins.plugins.business_rules import get_rules
from plugins.sync import sync
from tasks.models import ObjectSet


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
                    permission_objects.append(permission.pk)

        return permission_objects

    def handle(self, *args, **options):
        self.setup_kat_groups()
        self.seed_objects()
        self.seed_finding_types()
        self.sync_orgs()
        sync()
        self.seed_business_rules()

        logging.info("OpenKAT has been setup successfully")

    def setup_kat_groups(self):
        group_client, _ = Group.objects.get_or_create(name=GROUP_READ_ONLY)
        perms = self.get_permissions(
            [
                "view_organization",
                "view_organizationtag",
                "view_organizationmember",
                "view_objectset",
                "view_schedule",
                "view_task",
                "view_plugin",
                "view_businessrule",
                "view_network",
                "view_networkorganization",
                "view_ipaddress",
                "view_ipaddressorganization",
                "view_ipport",
                "view_hostname",
                "view_hostnameorganization",
                "view_findingtype",
                "view_finding",
                "view_findingorganization",
                "view_dnsarecord",
                "view_dnsaaaarecord",
                "view_dnsptrrecord",
                "view_dnscnamerecord",
                "view_dnsmxrecord",
                "view_dnsnsrecord",
                "view_dnscaarecord",
                "view_dnstxtrecord",
                "view_dnssrvrecord",
                "view_software",
                "view_report",
            ]
        )
        group_client.permissions.set(perms)
        group_admin, _ = Group.objects.get_or_create(name=GROUP_ADMIN)
        admin_perms = self.get_permissions(
            [
                # Custom permissions
                "download_file",
                "run_plugin",
                "run_businessrule",
                "can_access_all_organizations",
                "can_set_clearance_level",
                "can_scan_organization",
                "can_enable_disable_schedule",
                # Generic write permissions
                "add_objectset",
                "change_objectset",
                "delete_objectset",
                "add_schedule",
                "change_schedule",
                "delete_schedule",
                "add_task",
                "change_task",
                "delete_task",
                "add_plugin",
                "change_plugin",
                "delete_plugin",
                "add_businessrule",
                "change_businessrule",
                "delete_businessrule",
                "add_network",
                "change_network",
                "delete_network",
                "add_networkorganization",
                "change_networkorganization",
                "delete_networkorganization",
                "add_ipaddress",
                "change_ipaddress",
                "delete_ipaddress",
                "add_ipaddressorganization",
                "change_ipaddressorganization",
                "delete_ipaddressorganization",
                "add_ipport",
                "change_ipport",
                "delete_ipport",
                "add_hostname",
                "change_hostname",
                "delete_hostname",
                "add_hostnameorganization",
                "change_hostnameorganization",
                "delete_hostnameorganization",
                "add_findingtype",
                "change_findingtype",
                "delete_findingtype",
                "add_finding",
                "change_finding",
                "delete_finding",
                "add_findingorganization",
                "change_findingorganization",
                "delete_findingorganization",
                "add_report",
                "change_report",
                "delete_report",
            ]
        )
        group_admin.permissions.set(perms + admin_perms)

    def seed_objects(self):
        Network.objects.get_or_create(name="internet", declared=True)
        ObjectSet.objects.get_or_create(
            name="mail_server",
            description="Mail servers are hostnames that have an MX record pointed to them.",
            object_type=ContentType.objects.get_for_model(Hostname),
            object_query=Hostname.Q.mail_server,
        )
        ObjectSet.objects.get_or_create(
            name="name_server",
            description="Name servers are hostnames that have an NS record pointed to them.",
            object_type=ContentType.objects.get_for_model(Hostname),
            object_query=Hostname.Q.name_server,
        )
        ObjectSet.objects.get_or_create(
            name="root_domains",
            description="Root domains are hostnames that represent the registered domain (e.g., example.com).",
            object_type=ContentType.objects.get_for_model(Hostname),
            object_query=Hostname.Q.root_domain,
        )

    def seed_finding_types(self):
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        finding_types_path = base_dir / "plugins" / "plugins" / "finding_types.json"

        if not finding_types_path.exists():
            self.stdout.write(self.style.WARNING(f"Finding types file not found at {finding_types_path}"))
            return

        with finding_types_path.open() as f:
            finding_types_data = json.load(f)

        for code, data in finding_types_data.items():
            FindingType.objects.create(
                code=code,
                name=data.get("name"),
                description=data.get("description"),
                source=data.get("source"),
                risk=data.get("risk"),
                impact=data.get("impact"),
                recommendation=data.get("recommendation"),
                score=SEVERITY_SCORE_LOOKUP.get(data.get("risk", "").lower()),
            )

    def sync_orgs(self):
        for org in Organization.objects.all():
            org.save()

    def seed_business_rules(self):
        for rule_data in get_rules().values():
            rule, created = BusinessRule.objects.update_or_create(
                name=rule_data["name"],
                defaults={
                    "description": rule_data["description"],
                    "enabled": True,
                    "finding_type_code": rule_data["finding_type_code"],
                    "object_type": ContentType.objects.get_for_model(object_type_by_name()[rule_data["object_type"]]),
                    "query": rule_data["query"],
                    "inverse_query": rule_data.get("inverse_query"),
                },
            )
            rule.requires.set([Plugin.objects.get(plugin_id=require) for require in rule_data.get("requires", [])])
            rule.save()

        logging.info("Business rules seeded successfully")
