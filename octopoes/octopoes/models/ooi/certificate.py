from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Literal

import yaml

from octopoes.models import OOI, Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddress
from octopoes.models.persistence import ReferenceField


class AlgorithmType(Enum):
    """Represents the Algorithm Type from TLS certificates.

    Possible values
    ---------------
    RSA, ECC
    """

    RSA = "RSA"
    ECC = "ECC"


class X509Certificate(OOI):
    """Represents X509 certificates.

    Possible values
    ---------------
    Subject, issuer, valid from, valid intil, PK Algorithm, PK size, PK number, serial number,
    expires in
    """

    object_type: Literal["X509Certificate"] = "X509Certificate"

    subject: str | None = None
    issuer: str | None = None
    valid_from: str
    valid_until: str
    pk_algorithm: str | None = None
    pk_size: int | None = None
    pk_number: str | None = None
    signed_by: Reference | None = ReferenceField(
        "X509Certificate", max_issue_scan_level=1, max_inherit_scan_level=0, default=None
    )
    serial_number: str
    expires_in: timedelta | None = None

    _natural_key_attrs = ["issuer", "serial_number"]

    @property
    def expired(self):
        return datetime.now() > datetime.fromisoformat(self.valid_until)

    _reverse_relation_names = {"signed_by": "signed_certificates"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"{reference.tokenized.issuer} ({reference.tokenized.serial_number})"

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: X509Certificate) -> yaml.Node:
        return dumper.represent_mapping(
            "!X509Certificate",
            {
                **cls.get_ooi_yml_repr_dict(data),
                "subject": data.subject,
                "issuer": data.issuer,
                "valid_from": data.valid_from,
                "valid_until": data.valid_until,
                "pk_algorithm": data.pk_algorithm,
                "pk_size": data.pk_size,
                "pk_number": data.pk_number,
                "signed_by": data.signed_by,
                "serial_number": data.serial_number,
                "expires_in": data.expires_in,
            },
        )


class SubjectAlternativeName(OOI):
    """Represents alternative subject names in X509 Certificate objects."""

    certificate: Reference = ReferenceField(X509Certificate)

    _natural_key_attrs = ["certificate"]

    @classmethod
    def yml_constructor(cls, loader: yaml.SafeLoader, node):
        values: dict = loader.construct_mapping(node)
        if values.get("hostname"):
            return SubjectAlternativeNameHostname(**values)
        if values.get("address"):
            return SubjectAlternativeNameIP(**values)
        if values.get("name"):
            return SubjectAlternativeNameQualifier(**values)
        # raise ValueError("Falsy SubjectAlternativeName data provided.")


class SubjectAlternativeNameHostname(SubjectAlternativeName):
    """Represents subject alternative names for hostnames in X509 Certificate objects.

    Possible values
    ---------------
    hostnames

    Example value
    -------------
    mispo.es
    """

    object_type: Literal["SubjectAlternativeNameHostname"] = "SubjectAlternativeNameHostname"
    hostname: Reference = ReferenceField(Hostname, max_issue_scan_level=1, max_inherit_scan_level=0)

    _natural_key_attrs = ["certificate", "hostname"]

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return reference.tokenized.hostname.name

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: SubjectAlternativeNameHostname) -> yaml.Node:
        return dumper.represent_mapping(
            "!SubjectAlternativeNameHostname",
            {**cls.get_ooi_yml_repr_dict(data), "certificate": data.certificate, "hostname": data.hostname},
        )

    @classmethod
    def yml_constructor(cls, loader: yaml.SafeLoader, node):
        values: dict = loader.construct_mapping(node)
        return cls(**values)


class SubjectAlternativeNameIP(SubjectAlternativeName):
    """Represents subject alternative names for IPs in X509 Certificate objects.

    Possible values
    ---------------
    IPv4 or IPv6 address

    Example value
    -------------
    192.168.1.1
    """

    object_type: Literal["SubjectAlternativeNameIP"] = "SubjectAlternativeNameIP"
    address: Reference = ReferenceField(IPAddress)

    _natural_key_attrs = ["certificate", "address"]

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return reference.tokenized.address.address

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: SubjectAlternativeNameIP) -> yaml.Node:
        return dumper.represent_mapping(
            "!SubjectAlternativeNameIP",
            {**cls.get_ooi_yml_repr_dict(data), "certificate": data.certificate, "address": data.address},
        )

    @classmethod
    def yml_constructor(cls, loader: yaml.SafeLoader, node):
        values: dict = loader.construct_mapping(node)
        return cls(**values)


class SubjectAlternativeNameQualifier(SubjectAlternativeName):
    """Represents subject alternative names qualifier in X509 Certificate objects.

    Possible values
    ---------------
    hostnames

    Example value
    -------------
    mispo.es
    """

    object_type: Literal["SubjectAlternativeNameQualifier"] = "SubjectAlternativeNameQualifier"
    name: str

    _natural_key_attrs = ["certificate", "name"]

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return reference.tokenized.name

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: SubjectAlternativeNameQualifier) -> yaml.Node:
        return dumper.represent_mapping(
            "!SubjectAlternativeNameQualifier",
            {**cls.get_ooi_yml_repr_dict(data), "certificate": data.certificate, "name": data.name},
        )

    @classmethod
    def yml_constructor(cls, loader: yaml.SafeLoader, node):
        values: dict = loader.construct_mapping(node)
        return cls(**values)


X509Certificate.model_rebuild()
SubjectAlternativeNameHostname.model_rebuild()
SubjectAlternativeNameIP.model_rebuild()
SubjectAlternativeNameQualifier.model_rebuild()
