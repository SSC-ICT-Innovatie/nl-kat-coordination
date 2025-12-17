from typing import Any

from django.core.management.base import BaseCommand

from objects.models import (
    CAATag,
    DNSARecord,
    DNSCAARecord,
    DNSMXRecord,
    DNSNSRecord,
    DNSTXTRecord,
    Hostname,
    IPAddress,
    IPPort,
    Network,
    Protocol,
)


class Command(BaseCommand):
    help = "Load demo data into the Object database"

    def handle(self, *_args: Any, **_options: Any) -> None:  # noqa: C901, PLR0912, PLR0915
        """Create demo data for the Object application."""
        self.stdout.write(self.style.SUCCESS("Loading demo data..."))

        # Create network
        network, created = Network.objects.get_or_create(name="internet")
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created network: {network.name}"))
        else:
            self.stdout.write(f"Network already exists: {network.name}")

        # Create IP addresses
        ip_addresses = ["192.0.2.1", "192.0.2.2"]
        created_ips = []

        for ip_addr in ip_addresses:
            ip, created = IPAddress.objects.get_or_create(ip_address=ip_addr, defaults={"network": network})
            created_ips.append(ip)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created IP address: {ip.ip_address}"))
            else:
                self.stdout.write(f"IP address already exists: {ip.ip_address}")

        # Create IP ports
        ports_data = [
            # TCP ports on 192.0.2.1
            {"ip": created_ips[0], "port": 22, "protocol": Protocol.TCP, "service": "ssh", "tls": False},
            {"ip": created_ips[0], "port": 80, "protocol": Protocol.TCP, "service": "http", "tls": False},
            {"ip": created_ips[0], "port": 443, "protocol": Protocol.TCP, "service": "https", "tls": True},
            {"ip": created_ips[0], "port": 3306, "protocol": Protocol.TCP, "service": "mysql", "tls": None},
            # TCP ports on 192.0.2.2
            {"ip": created_ips[1], "port": 80, "protocol": Protocol.TCP, "service": "http", "tls": False},
            {"ip": created_ips[1], "port": 443, "protocol": Protocol.TCP, "service": "https", "tls": True},
            {"ip": created_ips[1], "port": 25, "protocol": Protocol.TCP, "service": "smtp", "tls": False},
            {"ip": created_ips[1], "port": 587, "protocol": Protocol.TCP, "service": "smtp-submission", "tls": True},
            # UDP ports on both IPs
            {"ip": created_ips[0], "port": 53, "protocol": Protocol.UDP, "service": "dns", "tls": None},
            {"ip": created_ips[0], "port": 123, "protocol": Protocol.UDP, "service": "ntp", "tls": None},
            {"ip": created_ips[1], "port": 53, "protocol": Protocol.UDP, "service": "dns", "tls": None},
        ]

        for port_data in ports_data:
            port, created = IPPort.objects.get_or_create(
                ip_address=port_data["ip"],
                port=port_data["port"],
                protocol=port_data["protocol"],
                defaults={"service": port_data["service"], "tls": port_data["tls"]},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created port: {port}"))
            else:
                self.stdout.write(f"Port already exists: {port}")

        # Create hostnames
        hostnames_data = ["example.com", "example.org", "ns1.example.com", "ns2.example.com", "mail.example.com"]
        created_hostnames = []

        for hostname_name in hostnames_data:
            hostname, created = Hostname.objects.get_or_create(name=hostname_name, defaults={"network": network})
            created_hostnames.append(hostname)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created hostname: {hostname.name}"))
            else:
                self.stdout.write(f"Hostname already exists: {hostname.name}")

        # Create DNS A records
        # example.com -> 192.0.2.1
        dns_a1, created = DNSARecord.objects.get_or_create(
            hostname=created_hostnames[0], ip_address=created_ips[0], defaults={"ttl": 3600}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created DNS A record: {dns_a1}"))
        else:
            self.stdout.write(f"DNS A record already exists: {dns_a1}")

        # example.org -> 192.0.2.2
        dns_a2, created = DNSARecord.objects.get_or_create(
            hostname=created_hostnames[1], ip_address=created_ips[1], defaults={"ttl": 3600}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created DNS A record: {dns_a2}"))
        else:
            self.stdout.write(f"DNS A record already exists: {dns_a2}")

        # Create DNS NS records
        # example.com -> ns1.example.com
        dns_ns1, created = DNSNSRecord.objects.get_or_create(
            hostname=created_hostnames[0],  # example.com
            name_server=created_hostnames[2],  # ns1.example.com
            defaults={"ttl": 86400},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created DNS NS record: {dns_ns1}"))
        else:
            self.stdout.write(f"DNS NS record already exists: {dns_ns1}")

        # example.com -> ns2.example.com
        dns_ns2, created = DNSNSRecord.objects.get_or_create(
            hostname=created_hostnames[0],  # example.com
            name_server=created_hostnames[3],  # ns2.example.com
            defaults={"ttl": 86400},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created DNS NS record: {dns_ns2}"))
        else:
            self.stdout.write(f"DNS NS record already exists: {dns_ns2}")

        # Create DNS MX records
        # example.com -> mail.example.com
        dns_mx1, created = DNSMXRecord.objects.get_or_create(
            hostname=created_hostnames[0],  # example.com
            mail_server=created_hostnames[4],  # mail.example.com
            preference=10,
            defaults={"ttl": 3600},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created DNS MX record: {dns_mx1}"))
        else:
            self.stdout.write(f"DNS MX record already exists: {dns_mx1}")

        # example.org -> mail.example.com
        dns_mx2, created = DNSMXRecord.objects.get_or_create(
            hostname=created_hostnames[1],  # example.org
            mail_server=created_hostnames[4],  # mail.example.com
            preference=10,
            defaults={"ttl": 3600},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created DNS MX record: {dns_mx2}"))
        else:
            self.stdout.write(f"DNS MX record already exists: {dns_mx2}")

        # Create DNS CAA records
        # example.com CAA 0 issue "letsencrypt.org"
        dns_caa1, created = DNSCAARecord.objects.get_or_create(
            hostname=created_hostnames[0],  # example.com
            flags=0,
            tag=CAATag.ISSUE,
            value="letsencrypt.org",
            defaults={"ttl": 3600},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created DNS CAA record: {dns_caa1}"))
        else:
            self.stdout.write(f"DNS CAA record already exists: {dns_caa1}")

        # example.com CAA 0 issuewild "letsencrypt.org"
        dns_caa2, created = DNSCAARecord.objects.get_or_create(
            hostname=created_hostnames[0],  # example.com
            flags=0,
            tag=CAATag.ISSUEWILD,
            value="letsencrypt.org",
            defaults={"ttl": 3600},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created DNS CAA record: {dns_caa2}"))
        else:
            self.stdout.write(f"DNS CAA record already exists: {dns_caa2}")

        # example.com CAA 0 iodef "mailto:security@example.com"
        dns_caa3, created = DNSCAARecord.objects.get_or_create(
            hostname=created_hostnames[0],  # example.com
            flags=0,
            tag=CAATag.IODEF,
            value="mailto:security@example.com",
            defaults={"ttl": 3600},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created DNS CAA record: {dns_caa3}"))
        else:
            self.stdout.write(f"DNS CAA record already exists: {dns_caa3}")

        # Create DNS TXT records
        # example.com TXT "v=spf1 mx ~all" (SPF record)
        dns_txt1, created = DNSTXTRecord.objects.get_or_create(
            hostname=created_hostnames[0],  # example.com
            prefix="",
            value="v=spf1 mx ~all",
            defaults={"ttl": 3600},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created DNS TXT record (SPF): {dns_txt1}"))
        else:
            self.stdout.write(f"DNS TXT record (SPF) already exists: {dns_txt1}")

        # example.com TXT "google-site-verification=example123"
        dns_txt2, created = DNSTXTRecord.objects.get_or_create(
            hostname=created_hostnames[0],  # example.com
            prefix="",
            value="google-site-verification=example123",
            defaults={"ttl": 3600},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created DNS TXT record: {dns_txt2}"))
        else:
            self.stdout.write(f"DNS TXT record already exists: {dns_txt2}")

        # _dmarc.example.com TXT "v=DMARC1; p=none; rua=mailto:dmarc@example.com"
        dns_txt3, created = DNSTXTRecord.objects.get_or_create(
            hostname=created_hostnames[0],  # _dmarc.example.com
            prefix="_dmarc",
            value="v=DMARC1; p=none; rua=mailto:dmarc@example.com",
            defaults={"ttl": 3600},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created DNS TXT record (DMARC): {dns_txt3}"))
        else:
            self.stdout.write(f"DNS TXT record (DMARC) already exists: {dns_txt3}")

        self.stdout.write(self.style.SUCCESS("Demo data loading completed successfully!"))
