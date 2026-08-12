import hashlib
from enum import Enum
from typing import Literal

from octopoes.models import OOI, Reference
from octopoes.models.ooi.dns.records import DNSTXTRecord
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddress, NetBlock
from octopoes.models.persistence import ReferenceField


class DNSSPFRecord(OOI):
    """Represents the DNS SPF record.

    Example value
    -------------
    v=spf1 a mx ~all
    """

    object_type: Literal["DNSSPFRecord"] = "DNSSPFRecord"
    value: str
    ttl: int | None = None
    all: str | None = None
    exp: str | None = None
    dns_txt_record: Reference = ReferenceField(DNSTXTRecord, max_inherit_scan_level=1)

    _natural_key_attrs = ["dns_txt_record", "value"]
    _reverse_relation_names = {"dns_txt_record": "dns_spf_record"}

    @property
    def natural_key(self) -> str:
        sha = hashlib.sha1(self.value.encode("UTF-8")).hexdigest()
        key = super().natural_key
        return key.replace(self.value, sha)

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"SPF Record of {reference.tokenized.dns_txt_record.hostname.name}"


class MechanismQualifier(Enum):
    """Represents the SPF Mechanism Qualifiers: allow' fail, softfail or neutral
    to specify how e-mail should be handled.

    Specification: http://www.open-spf.org/SPF_Record_Syntax/#0.1

    Possible values
    ---------------
    +, -, ~, ?

    Example value
    -------------
    +
    """

    ALLOW = "+"
    FAIL = "-"
    SOFTFAIL = "~"
    NEUTRAL = "?"

    # the string representation maps to a human readable format of the qualifier
    def __str__(self):
        return {
            MechanismQualifier.ALLOW: "Allow",
            MechanismQualifier.FAIL: "Fail",
            MechanismQualifier.SOFTFAIL: "Softfail",
            MechanismQualifier.NEUTRAL: "Neutral",
        }[self]


class DNSSPFMechanism(OOI):
    """Represents the DNS SPF Mechanism

    Example value
    -------------
    +a
    """

    spf_record: Reference = ReferenceField(DNSSPFRecord, max_inherit_scan_level=1)
    mechanism: str


class DNSSPFMechanismIP(DNSSPFMechanism):
    """Represents the DNS SPF Mechanism for IPs.

    Possible values
    ---------------
    +ip4, +ip6

    Example value
    -------------
    +ip4
    """

    object_type: Literal["DNSSPFMechanismIP"] = "DNSSPFMechanismIP"

    ip: Reference = ReferenceField(IPAddress)
    qualifier: MechanismQualifier = MechanismQualifier.ALLOW

    _natural_key_attrs = ["spf_record", "mechanism", "ip", "qualifier"]
    _information_value = ["mechanism", "qualifier"]
    _reverse_relation_names = {"spf_record": "spf_ip_mechanisms"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return (
            f"SPF {reference.tokenized.qualifier}{reference.tokenized.mechanism}:{reference.tokenized.ip.address}"
            f" for {reference.tokenized.spf_record.dns_txt_record.hostname.name}"
        )


class DNSSPFMechanismHostname(DNSSPFMechanism):
    """Represents the DNS SPF Mechanism for Hostnames.

    Example value:
    --------------
    +a:mispo.es
    """

    object_type: Literal["DNSSPFMechanismHostname"] = "DNSSPFMechanismHostname"

    hostname: Reference = ReferenceField(Hostname)
    qualifier: MechanismQualifier = MechanismQualifier.ALLOW

    _natural_key_attrs = ["spf_record", "mechanism", "hostname", "qualifier"]
    _information_value = ["mechanism", "qualifier"]
    _reverse_relation_names = {"spf_record": "spf_hostname_mechanisms"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return (
            f"SPF {reference.tokenized.qualifier}{reference.tokenized.mechanism}:{reference.tokenized.hostname.name}"
            f" for {reference.tokenized.spf_record.dns_txt_record.hostname.name}"
        )


class DNSSPFMechanismNetBlock(DNSSPFMechanism):
    """Represents the DNS SPF Mechanism for net blocks.

    Example value:
    --------------
    +ip4:192.168.0.0/24
    """

    object_type: Literal["DNSSPFMechanismNetBlock"] = "DNSSPFMechanismNetBlock"

    netblock: Reference = ReferenceField(NetBlock)
    qualifier: MechanismQualifier = MechanismQualifier.ALLOW

    _natural_key_attrs = ["spf_record", "mechanism", "netblock", "qualifier"]
    _information_value = ["mechanism", "qualifier"]
    _reverse_relation_names = {"spf_record": "spf_netblock_mechanisms"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return (
            f"SPF {reference.tokenized.qualifier}{reference.tokenized.mechanism}:"
            f"{reference.tokenized.netblock.start_ip}/{reference.tokenized.netblock.mask}"
            f" for {reference.tokenized.spf_record.dns_txt_record.hostname.name}"
        )


class DMARCTXTRecord(OOI):
    """Represents the DMARC TXT record for a hostname.

    Example value:
    --------------
    v=DMARC1;p=none;rua=dmarc@mispo.es;ruf=dmarc@mispo.es
    """

    object_type: Literal["DMARCTXTRecord"] = "DMARCTXTRecord"
    value: str
    ttl: int | None
    hostname: Reference = ReferenceField(Hostname)

    _natural_key_attrs = ["value", "hostname"]
    _reverse_relation_names = {"hostname": "dmarc_txt_record"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"DMARC TXT Record of {reference.tokenized.hostname.name}"


class DKIMExists(OOI):
    """Represents whether a DKIM can exist by checking the DNS response of _domainkey.hostname."""

    object_type: Literal["DKIMExists"] = "DKIMExists"
    hostname: Reference = ReferenceField(Hostname)

    _natural_key_attrs = ["hostname"]
    _reverse_relation_names = {"hostname": "dkim_exists"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"DKIM Exists on {reference.tokenized.hostname.name}"


class DKIMSelector(OOI):
    """Represents the DKIM Selector object if present.

    Object is currently unused.
    """

    object_type: Literal["DKIMSelector"] = "DKIMSelector"
    selector: str
    hostname: Reference = ReferenceField(Hostname)

    _natural_key_attrs = ["selector", "hostname"]
    _reverse_relation_names = {"hostname": "dkim_selector"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"{reference.tokenized.selector} DKIM selector of {reference.tokenized.hostname.name}"


class DKIMKey(OOI):
    """Represents the value of the DKIM key."""

    object_type: Literal["DKIMKey"] = "DKIMKey"
    key: str
    dkim_selector: Reference = ReferenceField(DKIMSelector)

    _natural_key_attrs = ["key", "dkim_selector"]
    _reverse_relation_names = {"dkim_selector": "dkim_key"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return (
            f"DKIM key of {reference.tokenized.dkim_selector.selector} on "
            f"{reference.tokenized.dkim_selector.hostname.name}"
        )
