"""
Django management command to set up a test organization with OOIs and boefjes.

Usage:
    python manage.py setup_test_org
    python manage.py setup_test_org --code myorg --name "My Organization"
    python manage.py setup_test_org --clearance-level 2
"""

import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from httpx import HTTPError
from katalogus.client import get_katalogus_client

from octopoes.connector.octopoes import OctopoesAPIConnector
from octopoes.models import DeclaredScanProfile, ScanLevel
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import Network
from octopoes.models.ooi.web import URL
from rocky.bytes_client import get_bytes_client
from tools.models import Indemnification, Organization, OrganizationMember
from tools.ooi_helpers import create_ooi

User = get_user_model()


class Command(BaseCommand):
    help = "Set up a test organization with OOIs and enabled boefjes"

    def add_arguments(self, parser):
        parser.add_argument("--code", type=str, default="test-org", help="Organization code (default: test-org)")
        parser.add_argument(
            "--name", type=str, default="Test Organization", help="Organization name (default: Test Organization)"
        )
        parser.add_argument(
            "--user", type=str, default=None, help="User email to add as member (default: first superuser)"
        )
        parser.add_argument(
            "--clearance-level",
            type=int,
            default=4,
            choices=[0, 1, 2, 3, 4],
            help="Clearance level for OOIs (default: 4)",
        )
        parser.add_argument(
            "--hostname", type=str, default="example.com", help="Hostname to add as OOI (default: example.com)"
        )
        parser.add_argument("--skip-boefjes", action="store_true", help="Skip enabling boefjes")

    def handle(self, *args, **options):
        org_code = options["code"]
        org_name = options["name"]
        clearance_level = options["clearance_level"]
        hostname = options["hostname"]
        skip_boefjes = options["skip_boefjes"]

        self.stdout.write(self.style.MIGRATE_HEADING("Setting up test organization"))
        self.stdout.write(f"  Code: {org_code}")
        self.stdout.write(f"  Name: {org_name}")
        self.stdout.write(f"  Clearance level: {clearance_level}")
        self.stdout.write("")

        # Step 1: Get or create user
        user = self._get_user(options["user"])
        if not user:
            return

        # Step 2: Create organization
        org = self._create_organization(org_code, org_name)
        if not org:
            return

        # Step 3: Create organization member
        self._create_member(user, org, clearance_level)

        # Step 4: Create indemnification
        self._create_indemnification(user, org)

        # Step 5: Add OOIs
        self._add_oois(org_code, hostname, clearance_level)

        # Step 6: Enable boefjes
        if not skip_boefjes:
            self._enable_boefjes(org_code)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"✓ Organization '{org_code}' is ready!"))
        self.stdout.write(f"  URL: http://localhost:8000/en/{org_code}/")

    def _get_user(self, email):
        """Get user by email or first superuser."""
        if email:
            user = User.objects.filter(email=email).first()
            if not user:
                self.stdout.write(self.style.ERROR(f"✗ User '{email}' not found"))
                return None
        else:
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                self.stdout.write(self.style.ERROR("✗ No superuser found"))
                return None

        self.stdout.write(self.style.SUCCESS(f"✓ Using user: {user.email}"))
        return user

    def _create_organization(self, code, name):
        """Create organization (triggers signals for Katalogus/Octopoes)."""
        org, created = Organization.objects.get_or_create(code=code, defaults={"name": name})

        if created:
            self.stdout.write(self.style.SUCCESS(f"✓ Created organization: {code}"))
        else:
            self.stdout.write(self.style.WARNING(f"⚠ Organization already exists: {code}"))

        return org

    def _create_member(self, user, org, clearance_level):
        """Create organization member with clearance levels."""
        member, created = OrganizationMember.objects.get_or_create(user=user, organization=org)

        member.trusted_clearance_level = clearance_level
        member.acknowledged_clearance_level = clearance_level
        member.onboarded = True
        member.status = OrganizationMember.STATUSES.ACTIVE
        member.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"✓ Created member with clearance level {clearance_level}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"✓ Updated member clearance level to {clearance_level}"))

        return member

    def _create_indemnification(self, user, org):
        """Create indemnification record."""
        _, created = Indemnification.objects.get_or_create(user=user, organization=org)

        if created:
            self.stdout.write(self.style.SUCCESS("✓ Created indemnification"))
        else:
            self.stdout.write(self.style.WARNING("⚠ Indemnification already exists"))

    def _add_oois(self, org_code, hostname, clearance_level):
        """Add test OOIs to Octopoes with proof in bytes."""
        self.stdout.write("Adding OOIs...")

        octopoes = OctopoesAPIConnector(
            settings.OCTOPOES_API, client=org_code, timeout=settings.ROCKY_OUTGOING_REQUEST_TIMEOUT
        )
        bytes_client = get_bytes_client(org_code)

        valid_time = datetime.datetime.now(datetime.timezone.utc)

        # Network (usually already seeded by organization creation signal)
        network = Network(name="internet")
        try:
            create_ooi(octopoes, bytes_client, network, valid_time)
            self.stdout.write("  ✓ Network: internet")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  ⚠ Network: {e}"))

        # Hostname
        host = Hostname(name=hostname, network=network.reference)
        try:
            create_ooi(octopoes, bytes_client, host, valid_time)
            self.stdout.write(f"  ✓ Hostname: {hostname}")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  ⚠ Hostname: {e}"))

        # www subdomain
        www_host = Hostname(name=f"www.{hostname}", network=network.reference)
        try:
            create_ooi(octopoes, bytes_client, www_host, valid_time)
            self.stdout.write(f"  ✓ Hostname: www.{hostname}")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  ⚠ www.{hostname}: {e}"))

        # URL
        url = URL(raw=f"https://{hostname}/", network=network.reference)
        try:
            create_ooi(octopoes, bytes_client, url, valid_time)
            self.stdout.write(f"  ✓ URL: https://{hostname}/")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  ⚠ URL: {e}"))

        # Set clearance level on the hostname (not on network)
        if clearance_level > 0:
            try:
                scan_profile = DeclaredScanProfile(reference=host.reference, level=ScanLevel(clearance_level))
                octopoes.save_scan_profile(scan_profile, valid_time)
                self.stdout.write(f"  ✓ Set clearance level {clearance_level} on {host.reference}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  ⚠ Clearance level: {e}"))

    def _enable_boefjes(self, org_code):
        """Enable common boefjes for testing."""
        self.stdout.write("Enabling boefjes...")

        boefjes = [
            "dns-records",
            "dns-sec",
            "dns-zone",
            "ssl-certificates",
            "security_txt_downloader",
            "webpage-analysis",
            "snyk",
            "shodan_internetdb",
            "nmap",
            "testssl-sh-ciphers",
            "ssl-version",
            "masscan",
        ]

        katalogus = get_katalogus_client()

        for boefje_id in boefjes:
            try:
                katalogus.enable_boefje_by_id(org_code, boefje_id)
                self.stdout.write(f"  ✓ {boefje_id}")
            except HTTPError as e:
                self.stdout.write(self.style.WARNING(f"  ⚠ {boefje_id}: {e}"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  ⚠ {boefje_id}: {e}"))
