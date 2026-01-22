from __future__ import annotations

import hashlib
from enum import Enum
from typing import Literal

import yaml

from octopoes.models import OOI, Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddress, IPAddressV4, IPAddressV6
from octopoes.models.persistence import ReferenceField


class DNSRecord(OOI):
    """Represents the DNS record"""

    hostname: Reference = ReferenceField(Hostname, max_issue_scan_level=0, max_inherit_scan_level=2)
    dns_record_type: Literal["A", "AAAA", "CAA", "CNAME", "MX", "NS", "PTR", "SOA", "SRV", "TXT"]
    value: str
    ttl: int | None = None  # todo: validation

    _natural_key_attrs = ["hostname", "value"]
    _reverse_relation_names = {"hostname": "dns_records"}

    @classmethod
    def _get_record_type(cls) -> str:
        end_index = cls.__name__.index("Record")
        return cls.__name__[3:end_index]

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        dns_record_type = cls._get_record_type()
        return f"{reference.tokenized.hostname.name} {dns_record_type} {reference.tokenized.value}"

    @classmethod
    def yml_constructor(cls, loader: yaml.SafeLoader, node):
        """it should be overrice again in child classes"""
        values: dict = loader.construct_mapping(node)
        if values.get("dns_record_type") == "A":
            return DNSARecord(**values)
        if values.get("dns_record_type") == "AAAA":
            return DNSAAAARecord(**values)
        if values.get("dns_record_type") == "CAA":
            return DNSCAARecord(**values)
        if values.get("dns_record_type") == "CNAME":
            return DNSCNAMERecord(**values)
        if values.get("dns_record_type") == "MX":
            return DNSMXRecord(**values)
        if values.get("dns_record_type") == "NS":
            return DNSNSRecord(**values)
        if values.get("dns_record_type") == "PTR":
            return DNSPTRRecord(**values)
        if values.get("dns_record_type") == "SOA":
            return DNSSOARecord(**values)
        # if values.get('dns_record_type') == "SRV":
        #     return DNSARecord(**values)
        if values.get("dns_record_type") == "TXT":
            return DNSTXTRecord(**values)


class DNSARecord(DNSRecord):
    """Represents the DNS A record.

    Example value
    -------------
    134.209.85.72
    """

    object_type: Literal["DNSARecord"] = "DNSARecord"
    dns_record_type: Literal["A"] = "A"

    address: Reference = ReferenceField(IPAddressV4)

    _reverse_relation_names = {"hostname": "dns_a_records", "address": "dns_a_records"}

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: DNSARecord) -> yaml.Node:
        return dumper.represent_mapping(
            "!DNSARecord",
            {
                **cls.get_ooi_yml_repr_dict(data),
                "hostname": data.hostname,
                "dns_record_type": data.dns_record_type,
                "value": data.value,
                "ttl": data.ttl,
                "address": data.address,
            },
        )

    @classmethod
    def yml_constructor(cls, loader: yaml.SafeLoader, node):
        values: dict = loader.construct_mapping(node)
        return cls(**values)


class DNSAAAARecord(DNSRecord):
    """Represents the DNS AAAA record.

    Example value
    -------------
    2001:0002:6c::430
    """

    object_type: Literal["DNSAAAARecord"] = "DNSAAAARecord"
    dns_record_type: Literal["AAAA"] = "AAAA"

    address: Reference = ReferenceField(IPAddressV6)

    _reverse_relation_names = {"hostname": "dns_aaaa_records", "address": "dns_aaaa_records"}

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: DNSAAAARecord) -> yaml.Node:
        return dumper.represent_mapping(
            "!DNSAAAARecord",
            {
                **cls.get_ooi_yml_repr_dict(data),
                "hostname": data.hostname,
                "value": data.value,
                "ttl": data.ttl,
                "dns_record_type": data.dns_record_type,
                "address": data.address,
            },
        )

    @classmethod
    def yml_constructor(cls, loader: yaml.SafeLoader, node):
        values: dict = loader.construct_mapping(node)
        return cls(**values)


class DNSMXRecord(DNSRecord):
    """Represents the DNS MX record."""

    object_type: Literal["DNSMXRecord"] = "DNSMXRecord"
    dns_record_type: Literal["MX"] = "MX"

    mail_hostname: Reference | None = ReferenceField(Hostname, default=None, max_inherit_scan_level=1)
    preference: int | None = None

    _reverse_relation_names = {"hostname": "dns_mx_records", "mail_hostname": "mail_server_of"}

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: DNSMXRecord) -> yaml.Node:
        return dumper.represent_mapping(
            "!DNSMXRecord",
            {
                **cls.get_ooi_yml_repr_dict(data),
                "hostname": data.hostname,
                "value": data.value,
                "ttl": data.ttl,
                "dns_record_type": data.dns_record_type,
                "mail_hostname": data.mail_hostname,
                "preference": data.preference,
            },
        )

    @classmethod
    def yml_constructor(cls, loader: yaml.SafeLoader, node):
        values: dict = loader.construct_mapping(node)
        return cls(**values)


class DNSTXTRecord(DNSRecord):
    """Represents the DNS TXT riecord.

    Example value
    -------------
    v=DMARC1;p=none;rua=dmarc@mispo.es;ruf=dmarc@mispo.es
    """

    object_type: Literal["DNSTXTRecord"] = "DNSTXTRecord"
    dns_record_type: Literal["TXT"] = "TXT"

    @property
    def natural_key(self) -> str:
        sha = hashlib.sha1(self.value.encode("UTF-8")).hexdigest()
        key = super().natural_key
        return key.replace(self.value, sha)

    _reverse_relation_names = {"hostname": "dns_txt_records"}

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: DNSTXTRecord) -> yaml.Node:
        return dumper.represent_mapping(
            "!DNSTXTRecord",
            {
                **cls.get_ooi_yml_repr_dict(data),
                "hostname": data.hostname,
                "value": data.value,
                "ttl": data.ttl,
                "dns_record_type": data.dns_record_type,
            },
        )

    @classmethod
    def yml_constructor(cls, loader: yaml.SafeLoader, node):
        values: dict = loader.construct_mapping(node)
        return cls(**values)


class DNSNSRecord(DNSRecord):
    """Represents the DNS NS record.

    Example value
    -------------
    ns0.transip.net
    """

    object_type: Literal["DNSNSRecord"] = "DNSNSRecord"
    dns_record_type: Literal["NS"] = "NS"

    name_server_hostname: Reference = ReferenceField(Hostname, max_issue_scan_level=1, max_inherit_scan_level=0)

    _reverse_relation_names = {"hostname": "dns_ns_records", "name_server_hostname": "ns_record_targets"}

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: DNSNSRecord) -> yaml.Node:
        return dumper.represent_mapping(
            "!DNSNSRecord",
            {
                **cls.get_ooi_yml_repr_dict(data),
                "hostname": data.hostname,
                "value": data.value,
                "ttl": data.ttl,
                "dns_record_type": data.dns_record_type,
                "name_server_hostname": data.name_server_hostname,
            },
        )

    @classmethod
    def yml_constructor(cls, loader: yaml.SafeLoader, node):
        values: dict = loader.construct_mapping(node)
        return cls(**values)


class DNSCNAMERecord(DNSRecord):
    """Represents the DNS CNAME record."""

    object_type: Literal["DNSCNAMERecord"] = "DNSCNAMERecord"
    dns_record_type: Literal["CNAME"] = "CNAME"

    target_hostname: Reference = ReferenceField(Hostname)

    _reverse_relation_names = {"hostname": "dns_cname_records", "target_hostname": "cname_target_of"}

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: DNSCNAMERecord) -> yaml.Node:
        return dumper.represent_mapping(
            "!DNSCNAMERecord",
            {
                **cls.get_ooi_yml_repr_dict(data),
                "hostname": data.hostname,
                "value": data.value,
                "ttl": data.ttl,
                "dns_record_type": data.dns_record_type,
                "target_hostname": data.target_hostname,
            },
        )

    @classmethod
    def yml_constructor(cls, loader: yaml.SafeLoader, node):
        values: dict = loader.construct_mapping(node)
        return cls(**values)


class DNSSOARecord(DNSRecord):
    """Represents the DNS SOA record.

    Example value
    -------------
    ns1.domaindiscount24.net. tech.key-systems.net. 2023012324 10800 3600 604800 3600
    """

    object_type: Literal["DNSSOARecord"] = "DNSSOARecord"
    dns_record_type: Literal["SOA"] = "SOA"

    soa_hostname: Reference = ReferenceField(Hostname)
    serial: int | None = None
    retry: int | None = None
    refresh: int | None = None
    expire: int | None = None
    minimum: int | None = None

    _reverse_relation_names = {"hostname": "dns_soa_records", "soa_hostname": "subject_of_dns_soa_records"}

    _natural_key_attrs = ["hostname", "soa_hostname"]

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        dns_record_type = cls._get_record_type()
        return f"{reference.tokenized.hostname.name} {dns_record_type} {reference.tokenized.soa_hostname.name}"

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: DNSSOARecord) -> yaml.Node:
        return dumper.represent_mapping(
            "!DNSSOARecord",
            {
                **cls.get_ooi_yml_repr_dict(data),
                "hostname": data.hostname,
                "value": data.value,
                "ttl": data.ttl,
                "dns_record_type": data.dns_record_type,
                "soa_hostname": data.soa_hostname,
                "serial": data.serial,
                "retry": data.retry,
                "refresh": data.refresh,
                "expire": data.expire,
                "minimum": data.minimum,
            },
        )

    @classmethod
    def yml_constructor(cls, loader: yaml.SafeLoader, node):
        values: dict = loader.construct_mapping(node)
        return cls(**values)


class NXDOMAIN(OOI):
    """Represents non-existing domains."""

    object_type: Literal["NXDOMAIN"] = "NXDOMAIN"

    hostname: Reference = ReferenceField(Hostname)

    _natural_key_attrs = ["hostname"]
    _reverse_relation_names = {"hostname": "nxdomain_hostname"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"NXDOMAIN response on {reference.tokenized.hostname.name}"

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: NXDOMAIN) -> yaml.Node:
        return dumper.represent_mapping("!NXDOMAIN", {**cls.get_ooi_yml_repr_dict(data), "hostname": data.hostname})


class DNSPTRRecord(DNSRecord):
    """Represents DNS PTR records."""

    object_type: Literal["DNSPTRRecord"] = "DNSPTRRecord"
    dns_record_type: Literal["PTR"] = "PTR"
    address: Reference | None = ReferenceField(IPAddress)

    _natural_key_attrs = ["hostname", "address"]

    _reverse_relation_names = {"hostname": "dns_ptr_records", "address": "ptr_record_ip"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"{reference.tokenized.address.address} -> {reference.tokenized.hostname.name}"

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: DNSPTRRecord) -> yaml.Node:
        return dumper.represent_mapping(
            "!DNSPTRRecord",
            {
                **cls.get_ooi_yml_repr_dict(data),
                "hostname": data.hostname,
                "value": data.value,
                "ttl": data.ttl,
                "dns_record_type": data.dns_record_type,
                "address": data.address,
            },
        )

    @classmethod
    def yml_constructor(cls, loader: yaml.SafeLoader, node):
        values: dict = loader.construct_mapping(node)
        return cls(**values)


class CAATAGS(Enum):
    """Represents CAA tags.

    Possible values
    ---------------
    issue, issuewild, iodef, contactemail, contactphone, issuevmc, issuemail
    """

    ISSUE = "issue"
    ISSUEWILD = "issuewild"
    IODEF = "iodef"
    CONTACTEMAIL = "contactemail"
    CONACTPHONE = "contactphone"
    ISSUEVMC = "issuevmc"
    ISSUEMAIL = "issuemail"

    def __str__(self) -> str:
        return self.value


class DNSCAARecord(DNSRecord):
    """Represents the DNS CAA record.

    Example value
    -------------
    "letsencrypt.org"
    """

    object_type: Literal["DNSCAARecord"] = "DNSCAARecord"
    dns_record_type: Literal["CAA"] = "CAA"

    # https://datatracker.ietf.org/doc/html/rfc8659#name-canonical-presentation-form
    # An unsigned integer between 0 and 255.
    flags: int | None = None

    # A non-zero-length sequence of ASCII letters and numbers in lowercase.
    tag: CAATAGS

    # The Value field, expressed as either (1) a contiguous set of characters
    # without interior spaces or (2) a quoted string.
    value: str
    _natural_key_attrs = ["hostname", "flags", "tag", "value"]

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: DNSCAARecord) -> yaml.Node:
        return dumper.represent_mapping(
            "!DNSCAARecord",
            {
                **cls.get_ooi_yml_repr_dict(data),
                "hostname": data.hostname,
                "value": data.value,
                "ttl": data.ttl,
                "dns_record_type": data.dns_record_type,
                "flags": data.flags,
                "tag": data.tag.value,
            },
        )

    @classmethod
    def yml_constructor(cls, loader: yaml.SafeLoader, node):
        values: dict = loader.construct_mapping(node)
        return cls(**values)
