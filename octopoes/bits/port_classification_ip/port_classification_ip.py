from collections.abc import Iterator
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.network import IPPort, Protocol

COMMON_TCP_PORTS = [
    25,  # SMTP
    53,  # DNS
    80,  # HTTP
    110,  # POP3
    143,  # IMAP
    443,  # HTTPS
    465,  # SMTPS
    587,  # SMTP (message submmission)
    993,  # IMAPS
    995,  # POP3S
]

COMMON_UDP_PORTS = [
    53  # DNS
]

SA_TCP_PORTS = [
    21,  # FTP
    22,  # SSH
    23,  # Telnet
    5900,  # VNC
]
DB_TCP_PORTS = [
    1433,  # MS SQL Server
    1434,  # MS SQL Server
    3050,  # Interbase/Firebase
    3306,  # MySQL
    5432,  # PostgreSQL
]
MICROSOFT_RDP_PORTS = [
    3389  # Microsoft Remote Desktop
]

# Ports that should never be exposed to the internet, with the reason.
# These are services that are unauthenticated by default, expose data,
# or allow remote code execution.
DANGEROUS_PORTS = {
    2375: "Docker API without TLS — allows remote code execution",
    2376: "Docker API — should not be exposed to the internet",
    2379: "etcd — exposes cluster state and secrets",
    2380: "etcd peer port — exposes cluster state and secrets",
    5984: "CouchDB — unauthenticated by default, exposes data",
    6379: "Redis — unauthenticated by default, exposes data",
    9200: "Elasticsearch — unauthenticated by default, exposes data",
    9300: "Elasticsearch transport — exposes cluster internals",
    10250: "Kubernetes kubelet — allows code execution on cluster nodes",
    10255: "Kubernetes kubelet read-only — exposes cluster internals",
    11211: "Memcached — unauthenticated, used in amplification attacks",
    27017: "MongoDB — unauthenticated by default, exposes data",
    50070: "Hadoop NameNode — exposes filesystem metadata",
    9000: "Hadoop NameNode IPC — exposes filesystem control",
}

# Insecure protocols that should be replaced with encrypted alternatives.
INSECURE_PORTS = {
    21: "FTP — transmits credentials in cleartext, use SFTP/FTPS instead",
    23: "Telnet — transmits credentials in cleartext, use SSH instead",
    69: "TFTP — unauthenticated, use SFTP instead",
    161: "SNMP — exposes device information, restrict to internal networks",
    389: "LDAP — unencrypted, use LDAPS (636) instead",
}


def get_ports_from_config(config, config_key, default):
    ports = config.get(config_key, None)
    if ports is None:
        return default
    return list(map(int, ports.split(","))) if ports else []


def run(input_ooi: IPPort, additional_oois: list, config: dict[str, Any]) -> Iterator[OOI]:
    aggregate_findings = config.get("aggregate_findings", "False").lower() == "true" if config else False
    open_ports = []

    common_tcp_ports = get_ports_from_config(config, "common_tcp_ports", COMMON_TCP_PORTS)
    common_udp_ports = get_ports_from_config(config, "common_udp_ports", COMMON_UDP_PORTS)
    sa_tcp_ports = get_ports_from_config(config, "sa_tcp_ports", SA_TCP_PORTS)
    db_tcp_ports = get_ports_from_config(config, "db_tcp_ports", DB_TCP_PORTS)
    microsoft_rdp_ports = get_ports_from_config(config, "microsoft_rdp_ports", MICROSOFT_RDP_PORTS)
    dangerous_ports = get_ports_from_config(config, "dangerous_ports", list(DANGEROUS_PORTS))
    insecure_ports = get_ports_from_config(config, "insecure_ports", list(INSECURE_PORTS))

    for ip_port in additional_oois:
        port = ip_port.port
        protocol = ip_port.protocol
        if port in dangerous_ports:
            ft = KATFindingType(id="KAT-DANGEROUS-PORT")
            if aggregate_findings:
                open_ports.append(ip_port.port)
            else:
                yield ft
                yield Finding(
                    finding_type=ft.reference,
                    ooi=ip_port.reference,
                    description=f"Port {port}/{protocol.value}: "
                    f"{DANGEROUS_PORTS.get(port, 'dangerous service')}. "
                    f"This port should never be exposed to the internet.",
                )
        elif port in insecure_ports:
            ft = KATFindingType(id="KAT-INSECURE-PROTOCOL")
            if aggregate_findings:
                open_ports.append(ip_port.port)
            else:
                yield ft
                yield Finding(
                    finding_type=ft.reference,
                    ooi=ip_port.reference,
                    description=f"Port {port}/{protocol.value}: {INSECURE_PORTS.get(port, 'insecure protocol')}.",
                )
        elif protocol == Protocol.TCP and port in sa_tcp_ports:
            open_sa_port = KATFindingType(id="KAT-OPEN-SYSADMIN-PORT")
            if aggregate_findings:
                open_ports.append(ip_port.port)
            else:
                yield open_sa_port
                yield Finding(
                    finding_type=open_sa_port.reference,
                    ooi=ip_port.reference,
                    description=f"Port {port}/{protocol.value} is a system administrator port and "
                    f"should possibly not be open.",
                )
        elif protocol == Protocol.TCP and port in db_tcp_ports:
            ft = KATFindingType(id="KAT-OPEN-DATABASE-PORT")
            if aggregate_findings:
                open_ports.append(ip_port.port)
            else:
                yield ft
                yield Finding(
                    finding_type=ft.reference,
                    ooi=ip_port.reference,
                    description=f"Port {port}/{protocol.value} is a database port and should not be open.",
                )
        elif port in microsoft_rdp_ports:
            open_rdp_port = KATFindingType(id="KAT-REMOTE-DESKTOP-PORT")
            if aggregate_findings:
                open_ports.append(ip_port.port)
            else:
                yield open_rdp_port
                yield Finding(
                    finding_type=open_rdp_port.reference,
                    ooi=ip_port.reference,
                    description=f"Port {port}/{protocol.value} is a Microsoft Remote Desktop port and "
                    f"should possibly not be open.",
                )
        elif (protocol == Protocol.TCP and port not in common_tcp_ports) or (
            protocol == Protocol.UDP and port not in common_udp_ports
        ):
            kat = KATFindingType(id="KAT-UNCOMMON-OPEN-PORT")
            if aggregate_findings:
                open_ports.append(ip_port.port)
            else:
                yield kat
                yield Finding(
                    finding_type=kat.reference,
                    ooi=ip_port.reference,
                    description=f"Port {port}/{protocol.value} is not a common port and should possibly not be open.",
                )
    if aggregate_findings and open_ports:
        ft = KATFindingType(id="KAT-UNCOMMON-OPEN-PORT")
        yield ft
        yield Finding(
            finding_type=ft.reference,
            ooi=input_ooi.reference,
            description=f"Ports {', '.join([str(port) for port in open_ports])} are not common ports and should "
            f"possibly not be open.",
        )
