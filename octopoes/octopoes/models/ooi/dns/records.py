import hashlib
from enum import Enum
from typing import Literal

from octopoes.models import OOI, Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddress, IPAddressV4, IPAddressV6
from octopoes.models.persistence import ReferenceField


class DNSRecord(OOI):
    """Represents the DNS record"""

    hostname: Reference = ReferenceField(Hostname, max_issue_scan_level=0, max_inherit_scan_level=2)
    dns_record_type: Literal["A", "AAAA", "CAA", "CNAME", "MX", "NS", "PTR", "SOA", "SRV", "TXT", "LOC", "GPOS"]
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


class DNSMXRecord(DNSRecord):
    """Represents the DNS MX record."""

    object_type: Literal["DNSMXRecord"] = "DNSMXRecord"
    dns_record_type: Literal["MX"] = "MX"

    mail_hostname: Reference | None = ReferenceField(Hostname, default=None, max_inherit_scan_level=1)
    preference: int | None = None

    _reverse_relation_names = {"hostname": "dns_mx_records", "mail_hostname": "mail_server_of"}


class DNSTXTRecord(DNSRecord):
    """Represents the DNS TXT record.

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


class DNSCNAMERecord(DNSRecord):
    """Represents the DNS CNAME record."""

    object_type: Literal["DNSCNAMERecord"] = "DNSCNAMERecord"
    dns_record_type: Literal["CNAME"] = "CNAME"

    target_hostname: Reference = ReferenceField(Hostname)

    _reverse_relation_names = {"hostname": "dns_cname_records", "target_hostname": "cname_target_of"}


class DNSSOARecord(DNSRecord):
    """Represents the DNS SOA record.

    Example value
    -------------
    ns1.domaindiscount24.net. tech.key-systems.net. 2023012324 10800 3600 604800 3600
    """

    object_type: Literal["DNSSOARecord"] = "DNSSOARecord"
    dns_record_type: Literal["SOA"] = "SOA"

    soa_hostname: Reference = ReferenceField(Hostname)
    rname: str | None = None
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


class NXDOMAIN(OOI):
    """Represents non-existing domains."""

    object_type: Literal["NXDOMAIN"] = "NXDOMAIN"

    hostname: Reference = ReferenceField(Hostname)

    _natural_key_attrs = ["hostname"]
    _reverse_relation_names = {"hostname": "nxdomain_hostname"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"NXDOMAIN response on {reference.tokenized.hostname.name}"


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


class DNSLocation(DNSRecord):
    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None  # in cm's

    @property
    def natural_key(self) -> str:
        sha = hashlib.sha1(self.value.encode()).hexdigest()
        key = super().natural_key
        return key.replace(self.value, sha)


class DNSGPOSRecord(DNSLocation):
    # RFC 1712
    object_type: Literal["DNSGPOSRecord"] = "DNSGPOSRecord"
    dns_record_type: Literal["GPOS"] = "GPOS"

    _reverse_relation_names = {"hostname": "dns_gpos_records"}


class DNSLOCRecord(DNSLocation):
    # RFC 1876
    object_type: Literal["DNSLOCRecord"] = "DNSLOCRecord"
    dns_record_type: Literal["LOC"] = "LOC"

    horizontal_precision: float | None = None  # in cms
    vertical_precision: float | None = None  # in cms
    size: float | None = None  # in cms

    _reverse_relation_names = {"hostname": "dns_loc_records"}
