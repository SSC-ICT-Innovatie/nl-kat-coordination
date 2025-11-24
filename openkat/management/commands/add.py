import sys
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management import BaseCommand

from files.models import File
from objects.models import Hostname, IPAddress, Network
from tasks.tasks import process_file


class Command(BaseCommand):
    help = """Add files and objects (hostnames, networks, IPs) to OpenKAT.

    Examples:
        # Upload file from stdin
        echo '123' | openkat add
        cat data.json | openkat add

        # Upload file from path
        openkat add /path/to/file

        # Add single hostname
        openkat add -H test.com

        # Add multiple hostnames from stdin
        cat hostnames.txt | openkat add -H
        echo -e "test.com\\nexample.org" | openkat add -H

        # Add single network
        openkat add -N 10.0.0.0/8

        # Add multiple networks from stdin
        cat networks.txt | openkat add -N

        # Add single IP address
        openkat add -I 192.168.1.1

        # Add multiple IPs from stdin
        cat ips.txt | openkat add -I
    """

    def add_arguments(self, parser):
        parser.add_argument("file_path", nargs="?", type=Path, help="Path to file to upload (if not using stdin)")
        parser.add_argument(
            "-H",
            "--hostname",
            nargs="?",
            const="STDIN",
            type=str,
            help="Add hostname(s). Use without value to read from stdin, or provide hostname directly.",
        )
        parser.add_argument(
            "-N",
            "--network",
            nargs="?",
            const="STDIN",
            type=str,
            help="Add network(s). Use without value to read from stdin, or provide network directly.",
        )
        parser.add_argument(
            "-I",
            "--ip",
            nargs="?",
            const="STDIN",
            type=str,
            help="Add IP address(es). Use without value to read from stdin, or provide IP directly.",
        )
        parser.add_argument(
            "--network-name",
            type=str,
            default="internet",
            help="Network to associate with hostnames and IPs (default: internet)",
        )

    def handle(self, *args, **options):
        file_path = options.get("file_path")
        hostname_arg = options.get("hostname")
        network_arg = options.get("network")
        ip_arg = options.get("ip")
        network_name = options.get("network_name")

        # Ensure the name network exists
        network_obj, _ = Network.objects.get_or_create(name=network_name)

        # Count flags to ensure only one operation at a time
        flags_count = sum([hostname_arg is not None, network_arg is not None, ip_arg is not None])

        # If no flags provided, treat as file upload
        if flags_count == 0:
            return self.handle_file_upload(file_path)

        # If multiple flags, error
        if flags_count > 1:
            self.stderr.write(self.style.ERROR("Error: Only one of -H, -N, or -I can be specified at a time."))
            return

        # Handle hostname
        if hostname_arg is not None:
            return self.handle_hostname(hostname_arg, network_obj)

        # Handle network
        if network_arg is not None:
            return self.handle_network(network_arg)

        # Handle IP
        if ip_arg is not None:
            return self.handle_ip(ip_arg, network_obj)

    def handle_file_upload(self, file_path):
        """Upload a file from path or stdin."""
        if file_path:
            # Upload from file path
            path = Path(file_path)
            if not path.exists():
                self.stderr.write(self.style.ERROR(f"Error: File '{file_path}' not found."))
                return

            content = path.read_bytes()
            file_name = path.name
        else:
            # Upload from stdin
            if sys.stdin.isatty():
                self.stderr.write(
                    self.style.ERROR(
                        "Error: No file path provided and stdin is empty. "
                        "Use 'echo data | openkat add' or 'openkat add /path/to/file'."
                    )
                )
                return

            content = sys.stdin.buffer.read()
            file_name = "stdin-upload"

        # Create file
        file_obj = File.objects.create(file=ContentFile(content, name=file_name))

        self.stdout.write(
            self.style.SUCCESS(f"File uploaded successfully: ID={file_obj.pk}, Path={file_obj.file.name}")
        )
        tasks = process_file(file_obj)
        self.stdout.write(self.style.SUCCESS(f"File processing started, created {len(tasks)} tasks"))

    def handle_hostname(self, hostname_arg, network_obj):
        """Add hostname(s) from argument or stdin."""
        if hostname_arg == "STDIN":
            # Read from stdin
            if sys.stdin.isatty():
                self.stderr.write(self.style.ERROR("Error: -H flag used without value but stdin is empty."))
                return

            hostnames = [line.strip() for line in sys.stdin if line.strip()]
        else:
            # Single hostname from argument
            hostnames = [hostname_arg]

        created_count = 0
        updated_count = 0

        for hostname in hostnames:
            hostname_obj, created = Hostname.objects.get_or_create(name=hostname, defaults={"network": network_obj})
            if created:
                created_count += 1
                self.stdout.write(f"Created hostname: {hostname}")
            else:
                updated_count += 1
                self.stdout.write(f"Hostname already exists: {hostname}")

        self.stdout.write(
            self.style.SUCCESS(f"\nHostnames processed: {created_count} created, {updated_count} already existed")
        )

    def handle_network(self, network_arg):
        """Add network(s) from argument or stdin."""
        if network_arg == "STDIN":
            # Read from stdin
            if sys.stdin.isatty():
                self.stderr.write(self.style.ERROR("Error: -N flag used without value but stdin is empty."))
                return

            networks = [line.strip() for line in sys.stdin if line.strip()]
        else:
            # Single network from argument
            networks = [network_arg]

        created_count = 0
        updated_count = 0

        for network in networks:
            network_obj, created = Network.objects.get_or_create(name=network)
            if created:
                created_count += 1
                self.stdout.write(f"Created network: {network}")
            else:
                updated_count += 1
                self.stdout.write(f"Network already exists: {network}")

        self.stdout.write(
            self.style.SUCCESS(f"\nNetworks processed: {created_count} created, {updated_count} already existed")
        )

    def handle_ip(self, ip_arg, network_obj):
        """Add IP address(es) from argument or stdin."""
        if ip_arg == "STDIN":
            # Read from stdin
            if sys.stdin.isatty():
                self.stderr.write(self.style.ERROR("Error: -I flag used without value but stdin is empty."))
                return

            ips = [line.strip() for line in sys.stdin if line.strip()]
        else:
            # Single IP from argument
            ips = [ip_arg]

        created_count = 0
        updated_count = 0

        for ip in ips:
            ip_obj, created = IPAddress.objects.get_or_create(address=ip, defaults={"network": network_obj})
            if created:
                created_count += 1
                self.stdout.write(f"Created IP: {ip}")
            else:
                updated_count += 1
                self.stdout.write(f"IP already exists: {ip}")

        self.stdout.write(
            self.style.SUCCESS(f"\nIPs processed: {created_count} created, {updated_count} already existed")
        )
