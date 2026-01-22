from __future__ import annotations

from typing import Literal

import yaml

from octopoes.models import OOI, Reference
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

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: Service) -> yaml.Node:
        return dumper.represent_mapping("!Service", {**cls.get_ooi_yml_repr_dict(data), "name": data.name})


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

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: IPService) -> yaml.Node:
        return dumper.represent_mapping(
            "!IPService", {**cls.get_ooi_yml_repr_dict(data), "ip_port": data.ip_port, "service": data.service}
        )


class TLSCipher(OOI):
    object_type: Literal["TLSCipher"] = "TLSCipher"

    ip_service: Reference = ReferenceField(IPService, max_issue_scan_level=0, max_inherit_scan_level=4)
    suites: dict

    _natural_key_attrs = ["ip_service"]

    _reverse_relation_names = {"ip_service": "ciphers"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        t = reference.tokenized
        ip_address = t.ip_service.ip_port.address.address
        return f"Ciphers of {str(ip_address)}:{t.ip_service.ip_port.port}"

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: TLSCipher) -> yaml.Node:
        return dumper.represent_mapping(
            "!TLSCipher", {**cls.get_ooi_yml_repr_dict(data), "ip_service": data.ip_service, "suites": data.suites}
        )
