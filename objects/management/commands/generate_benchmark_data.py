import random
import socket
import struct
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from objects.models import (
    DNSAAAARecord,
    DNSARecord,
    DNSCAARecord,
    DNSMXRecord,
    DNSNSRecord,
    DNSTXTRecord,
    Finding,
    FindingType,
    Hostname,
    IPAddress,
    IPPort,
    Network,
    Software,
    bulk_insert,
)
from openkat.management.commands.seed import Command as SeedCommand


def generate(
    N: int, hostname_scan_level: int, ipaddress_scan_level: int, include_dns_records: bool = False
) -> tuple[
    list[Hostname],
    list[IPAddress],
    list[IPPort],
    list[DNSARecord],
    list[DNSAAAARecord],
    list[DNSNSRecord],
    list[DNSMXRecord],
    list[DNSTXTRecord],
    list[DNSCAARecord],
    list[Finding],
    list[FindingType],
    list[Software],
]:
    network, created = Network.objects.get_or_create(name="internet")
    ips = []
    ips_v6 = []
    ports = []
    hostnames = []
    a_records = []
    aaaa_records = []
    ns_records = []
    mx_records = []
    txt_records = []
    caa_records = []
    findings = []
    finding_types = SeedCommand.seed_finding_types()
    by_code = {ft.code: ft for ft in finding_types}
    software = [Software(name="old-js-lib", version="v-2.1.3"), Software(name="old-wordpress-plugin", version="0.1")]

    for i in range(N):
        # IPv4
        ip = IPAddress(
            network=network,
            address=str(socket.inet_ntoa(struct.pack(">I", random.randint(1, 0xFFFFFFFF)))),  # noqa: S311
            scan_level=ipaddress_scan_level,
        )
        ips.append(ip)

        # Hostname
        hn = Hostname(network=network, name=f"test-{i}.com", scan_level=hostname_scan_level)
        hostnames.append(hn)

        # IPv6 (every 5th host gets IPv6)
        if include_dns_records and i % 5 == 0:
            ipv6 = IPAddress(network=network, address=f"2001:db8:{i:04x}::{i:04x}", scan_level=ipaddress_scan_level)
            ips_v6.append(ipv6)
            if i % 50 == 0:
                finding = Finding(finding_type=by_code["KAT-WEBSERVER-NO-IPV6"], hostname=hn)
                findings.append(finding)  # False finding

        # Ports
        http_port = IPPort(address=ip, protocol="TCP", port=80, service="http")
        ports.append(http_port)
        https_port = IPPort(address=ip, protocol="TCP", port=443, service="https")
        ports.append(https_port)

        if i % 1000 == 0:
            software[0].ports.add(https_port)

        if i % 200 == 0:
            finding = Finding(finding_type=by_code["KAT-OPEN-SYSADMIN-PORT"], address=ip)
            findings.append(finding)  # False finding
            finding = Finding(finding_type=by_code["KAT-OPEN-DATABASE-PORT"], address=ip)
            findings.append(finding)  # False finding
            finding = Finding(finding_type=by_code["KAT-REMOTE-DESKTOP-PORT"], address=ip)
            findings.append(finding)  # False finding
            finding = Finding(finding_type=by_code["KAT-UNCOMMON-OPEN-PORT"], address=ip)
            findings.append(finding)  # False finding
            finding = Finding(finding_type=by_code["KAT-OPEN-COMMON-PORT"], address=ip)
            findings.append(finding)  # True finding
            finding = Finding(finding_type=by_code["KAT-NO-DMARC"], hostname=hn)
            findings.append(finding)  # True finding
            finding = Finding(finding_type=by_code["KAT-DOMAIN-OWNERSHIP-PENDING"], hostname=hn)
            findings.append(finding)  # False finding

        # Add some varied ports for business rule testing
        if i % 10 == 0:
            ports.append(IPPort(address=ip, protocol="TCP", port=22, service="ssh"))  # Sysadmin port
        if i % 15 == 0:
            ports.append(IPPort(address=ip, protocol="TCP", port=3306, service="mysql"))  # Database port

        # DNS A Record for every 2nd host
        if i % 2 == 0:
            a_record = DNSARecord(hostname=hn, ip_address=ip, ttl=300)
            a_records.append(a_record)

        # Additional DNS records (for business rule testing)
        if include_dns_records:
            # AAAA records (IPv6) for every 5th host
            if i % 5 == 0 and ips_v6:
                aaaa_records.append(DNSAAAARecord(hostname=hn, ip_address=ips_v6[-1], ttl=300))

            # NS records for nameservers (every 20th)
            if i % 20 == 0 and i > 0:
                ns_hostname = Hostname(network=network, name=f"ns{i}.test.com", scan_level=hostname_scan_level)
                hostnames.append(ns_hostname)
                ns_records.append(DNSNSRecord(hostname=hn, name_server=ns_hostname, ttl=300))
                if i % 100 == 0:
                    finding = Finding(finding_type=by_code["KAT-NAMESERVER-NO-IPV6"], hostname=ns_hostname)
                    findings.append(finding)  # False finding
                    finding = Finding(finding_type=by_code["KAT-NAMESERVER-NO-TWO-IPV6"], hostname=hn)
                    findings.append(finding)

            # MX records for mail servers (every 10th)
            if i % 10 == 0 and i > 0:
                mx_hostname = Hostname(network=network, name=f"mail{i}.test.com")
                hostnames.append(mx_hostname)
                mx_records.append(DNSMXRecord(hostname=hn, mail_server=mx_hostname, preference=10, ttl=300))

            # TXT records (every 7th) - some with SPF
            if i % 7 == 0:
                if i % 14 == 0:
                    txt_records.append(DNSTXTRecord(hostname=hn, value="v=spf1 include:_spf.example.com ~all", ttl=300))
                    if i % 50 == 0:
                        finding = Finding(finding_type=by_code["KAT-NO-SPF"], hostname=hn)
                        findings.append(finding)  # False finding
                else:
                    txt_records.append(DNSTXTRecord(hostname=hn, value="v=DKIM1; k=rsa; p=...", ttl=300))

            # CAA records (every 25th)
            if i % 25 == 0:
                if i % 200 == 0:
                    finding = Finding(finding_type=by_code["KAT-NO-CAA"], hostname=hn)
                    findings.append(finding)  # False finding

                caa_records.append(DNSCAARecord(hostname=hn, flags=0, tag="issue", value="letsencrypt.org", ttl=300))

    return (
        hostnames,
        ips + ips_v6,
        ports,
        a_records,
        aaaa_records,
        ns_records,
        mx_records,
        txt_records,
        caa_records,
        findings,
        finding_types,
        software,
    )


class Command(BaseCommand):
    help = "Load many objects into XTDB"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("-n", dest="number_of_objects", type=int, default=100_000)
        parser.add_argument("-hs", dest="hostname_scan_level", type=int, default=2)
        parser.add_argument("-is", dest="ipaddress_scan_level", type=int, default=2)
        parser.add_argument(
            "--with-dns",
            "-d",
            dest="include_dns",
            action="store_true",
            help="Include additional DNS records for business rule testing",
        )

    def handle(
        self,
        number_of_objects: int,
        hostname_scan_level: int,
        ipaddress_scan_level: int,
        include_dns: bool = False,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.stdout.write(self.style.SUCCESS("Loading benchmark data..."))

        (
            hosts,
            ips,
            ports,
            arecords,
            aaaa_records,
            ns_records,
            mx_records,
            txt_records,
            caa_records,
            findings,
            _,
            software,
        ) = generate(number_of_objects, hostname_scan_level, ipaddress_scan_level, include_dns)

        self.stdout.write(self.style.SUCCESS("Loading hostnames..."))
        bulk_insert(hosts)

        self.stdout.write(self.style.SUCCESS("Loading ipaddresses..."))
        bulk_insert(ips)

        self.stdout.write(self.style.SUCCESS("Loading ipports..."))
        bulk_insert(ports)

        self.stdout.write(self.style.SUCCESS("Loading DNSArecords..."))
        bulk_insert(arecords)

        if include_dns:
            if aaaa_records:
                self.stdout.write(self.style.SUCCESS("Loading DNSAAAArecords..."))
                bulk_insert(aaaa_records)
            if ns_records:
                self.stdout.write(self.style.SUCCESS("Loading DNSNSrecords..."))
                bulk_insert(ns_records)
            if mx_records:
                self.stdout.write(self.style.SUCCESS("Loading DNSMXrecords..."))
                bulk_insert(mx_records)
            if txt_records:
                self.stdout.write(self.style.SUCCESS("Loading DNSTXTrecords..."))
                bulk_insert(txt_records)
            if caa_records:
                self.stdout.write(self.style.SUCCESS("Loading DNSCAArecords..."))
                bulk_insert(caa_records)

        self.stdout.write(self.style.SUCCESS("Loading Findings..."))
        bulk_insert(findings)

        self.stdout.write(self.style.SUCCESS("Loading Software..."))
        bulk_insert(software)

        self.stdout.write(self.style.SUCCESS("Done loading benchmark data"))
