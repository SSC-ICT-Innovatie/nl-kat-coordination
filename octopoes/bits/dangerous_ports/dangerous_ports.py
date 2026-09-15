from collections.abc import Iterator
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.network import IPPort, Protocol

# Ports that should never be exposed to the internet, with the reason.
# These are services that are unauthenticated by default, expose data,
# or allow remote code execution. port_classification_ip flags these as
# "uncommon" with a generic message; this bit gives a specific danger warning.
DANGEROUS_PORTS: dict[int, str] = {
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
INSECURE_PORTS: dict[int, str] = {
    21: "FTP — transmits credentials in cleartext, use SFTP/FTPS instead",
    23: "Telnet — transmits credentials in cleartext, use SSH instead",
    69: "TFTP — unauthenticated, use SFTP instead",
    161: "SNMP — exposes device information, restrict to internal networks",
    389: "LDAP — unencrypted, use LDAPS (636) instead",
}


def run(input_ooi: IPPort, additional_oois: list, config: dict[str, Any]) -> Iterator[OOI]:
    """Flag ports that should never be exposed to the internet.

    Complements port-classification-ip: that bit classifies ports into
    categories (sysadmin, database, RDP, uncommon) with soft language.
    This bit flags services that are dangerous by design — unauthenticated
    by default, exposing data, or allowing RCE — with a specific warning.
    """
    if input_ooi.protocol != Protocol.TCP:
        return

    port = input_ooi.port

    if port in DANGEROUS_PORTS:
        ft = KATFindingType(id="KAT-DANGEROUS-PORT")
        yield ft
        yield Finding(
            finding_type=ft.reference,
            ooi=input_ooi.reference,
            description=f"Port {port}/tcp: {DANGEROUS_PORTS[port]}. This port should never be exposed to the internet.",
        )
    elif port in INSECURE_PORTS:
        ft = KATFindingType(id="KAT-INSECURE-PROTOCOL")
        yield ft
        yield Finding(
            finding_type=ft.reference, ooi=input_ooi.reference, description=f"Port {port}/tcp: {INSECURE_PORTS[port]}."
        )
