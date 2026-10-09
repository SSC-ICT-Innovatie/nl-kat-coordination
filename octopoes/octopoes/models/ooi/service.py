from typing import Literal

from pydantic import Field

from octopoes.models import OOI, Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPPort
from octopoes.models.persistence import ReferenceField


class Service(OOI):
    object_type: Literal["Service"] = "Service"

    name: str

    _natural_key_attrs = ["name"]
    _information_value = ["name"]
    _traversable = False

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return reference.tokenized.name


class IPService(OOI):
    object_type: Literal["IPService"] = "IPService"

    ip_port: Reference = ReferenceField(IPPort, max_issue_scan_level=0, max_inherit_scan_level=4)
    service: Reference = ReferenceField(Service, max_issue_scan_level=1, max_inherit_scan_level=0)

    _natural_key_attrs = ["ip_port", "service"]

    _reverse_relation_names = {"ip_port": "services", "service": "services"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        t = reference.tokenized
        ip_address = t.ip_port.address.address
        return f"{t.service.name}://{ip_address}:{t.ip_port.port}/{t.ip_port.protocol}"


class HostnameService(OOI):
    """A named service exposed by an IP service.

    This is the generic hostname-to-IPService relationship used when a
    protocol may depend on the hostname (for example TLS SNI). It is not
    specific to HTTP.
    """

    object_type: Literal["HostnameService"] = "HostnameService"

    ip_service: Reference = ReferenceField(IPService, max_issue_scan_level=0, max_inherit_scan_level=4)
    hostname: Reference = ReferenceField(Hostname, max_issue_scan_level=0, max_inherit_scan_level=4)

    _natural_key_attrs = ["ip_service", "hostname"]
    _reverse_relation_names = {"ip_service": "hostname_services", "hostname": "services"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        # Natural key:
        #   network|address|protocol|port|service
        # or
        #   network|address|protocol|port|service|hostname_network|hostname
        t = reference.tokenized
        address = t.ip_service.ip_port.address.address
        port = t.ip_service.ip_port.port
        return f"{t.ip_service.service.name}://{t.hostname.name}:{port} @ {address}"


class TLSCipher(OOI):
    object_type: Literal["TLSCipher"] = "TLSCipher"

    ip_service: Reference = ReferenceField(IPService, max_issue_scan_level=0, max_inherit_scan_level=4)
    hostname: Reference | None = ReferenceField(
        Hostname, default=None, max_issue_scan_level=0, max_inherit_scan_level=4
    )
    suites: dict
    server_preference: dict[str, str] = Field(default_factory=dict)

    _natural_key_attrs = ["ip_service"]

    _reverse_relation_names = {"ip_service": "ciphers", "hostname": "ciphers"}

    @property
    def natural_key(self) -> str:
        # Keep the legacy IPService-only key stable for scans that do not have a
        # hostname, while hostname-aware observations become uniquely keyed by
        # (hostname, IPService).
        if self.hostname is None:
            return self.ip_service.natural_key
        return f"{self.ip_service.natural_key}|{self.hostname.natural_key}"

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        parts = reference.natural_key.split("|")

        address = parts[1]
        port = parts[3]

        if len(parts) == 7:
            hostname = parts[6]
            return f"Ciphers of {hostname}:{address}:{port}"

        return f"Ciphers of {address}:{port}"
