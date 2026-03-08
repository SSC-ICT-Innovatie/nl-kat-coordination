from __future__ import annotations

from collections.abc import Iterator
from functools import cache
from typing import TypeVar

from pydantic.fields import FieldInfo

from octopoes.models import OOI, Reference
from octopoes.models.exception import TypeNotFound
from octopoes.models.ooi.certificate import (
    SubjectAlternativeNameHostname,
    SubjectAlternativeNameIP,
    SubjectAlternativeNameQualifier,
    X509Certificate,
)
from octopoes.models.ooi.config import Config
from octopoes.models.ooi.dns.records import (
    NXDOMAIN,
    DNSAAAARecord,
    DNSARecord,
    DNSCAARecord,
    DNSCNAMERecord,
    DNSMXRecord,
    DNSNSRecord,
    DNSPTRRecord,
    DNSSOARecord,
    DNSTXTRecord,
)
from octopoes.models.ooi.dns.zone import DNSZone, Hostname, ResolvedHostname
from octopoes.models.ooi.email_security import (
    DKIMExists,
    DKIMKey,
    DKIMSelector,
    DMARCTXTRecord,
    DNSSPFMechanismHostname,
    DNSSPFMechanismIP,
    DNSSPFMechanismNetBlock,
    DNSSPFRecord,
)
from octopoes.models.ooi.findings import (
    ADRFindingType,
    CAPECFindingType,
    CVEFindingType,
    CWEFindingType,
    Finding,
    FindingType,
    KATFindingType,
    MutedFinding,
    RetireJSFindingType,
    SnykFindingType,
)
from octopoes.models.ooi.geography import GeographicPoint
from octopoes.models.ooi.monitoring import Application, Incident
from octopoes.models.ooi.network import (
    AutonomousSystem,
    IPAddress,
    IPAddressV4,
    IPAddressV6,
    IPPort,
    IPV4NetBlock,
    IPV6NetBlock,
    Network,
)
from octopoes.models.ooi.question import Question
from octopoes.models.ooi.reports import AssetReport, HydratedReport, Report, ReportData, ReportRecipe
from octopoes.models.ooi.scans import ExternalScan
from octopoes.models.ooi.service import IPService, Service, TLSCipher
from octopoes.models.ooi.software import Software, SoftwareInstance
from octopoes.models.ooi.web import (
    RESTAPI,
    URL,
    APIDesignRule,
    APIDesignRuleResult,
    HostnameHTTPURL,
    HTTPHeader,
    HTTPHeaderHostname,
    HTTPHeaderURL,
    HTTPResource,
    ImageMetadata,
    IPAddressHTTPURL,
    SecurityTXT,
    Website,
)

CertificateType = (
    X509Certificate | SubjectAlternativeNameHostname | SubjectAlternativeNameIP | SubjectAlternativeNameQualifier
)
DnsType = DNSZone | Hostname
DnsRecordType = (
    DNSARecord
    | DNSAAAARecord
    | DNSTXTRecord
    | DNSMXRecord
    | DNSNSRecord
    | DNSPTRRecord
    | DNSSOARecord
    | DNSCNAMERecord
    | DNSCAARecord
    | ResolvedHostname
    | NXDOMAIN
)
ConcreteFindingTypeType = (
    ADRFindingType
    | KATFindingType
    | CVEFindingType
    | RetireJSFindingType
    | CWEFindingType
    | CAPECFindingType
    | SnykFindingType
)
FindingTypeType = FindingType | ConcreteFindingTypeType
ConcreteNetworkType = Network | IPAddressV4 | IPAddressV6 | AutonomousSystem | IPV4NetBlock | IPV6NetBlock | IPPort
NetworkType = ConcreteNetworkType | IPAddress
ServiceType = Service | IPService | TLSCipher
SoftwareType = Software | SoftwareInstance
WebType = (
    Website
    | URL
    | HostnameHTTPURL
    | IPAddressHTTPURL
    | HTTPResource
    | HTTPHeader
    | HTTPHeaderURL
    | HTTPHeaderHostname
    | ImageMetadata
    | RESTAPI
    | APIDesignRule
    | APIDesignRuleResult
    | SecurityTXT
)
EmailSecurityType = (
    DNSSPFRecord
    | DNSSPFMechanismIP
    | DNSSPFMechanismHostname
    | DNSSPFMechanismNetBlock
    | DMARCTXTRecord
    | DKIMExists
    | DKIMSelector
    | DKIMKey
)
MonitoringType = Application | Incident
ConfigType = Config
ReportsType = ReportData
ScanType = ExternalScan

ConcreteOOIType = (
    CertificateType
    | DnsType
    | DnsRecordType
    | ConcreteNetworkType
    | ServiceType
    | SoftwareType
    | WebType
    | DNSSPFMechanismIP
    | DNSSPFMechanismHostname
    | DNSSPFMechanismNetBlock
    | DNSSPFRecord
    | MonitoringType
    | EmailSecurityType
    | Finding
    | MutedFinding
    | ConcreteFindingTypeType
    | ConfigType
    | Question
    | ReportsType
    | ScanType
    | Report
    | HydratedReport
    | AssetReport
    | GeographicPoint
    | ReportRecipe
)

OOIType = ConcreteOOIType | ConcreteNetworkType | ConcreteFindingTypeType
BITOOIType = ConcreteOOIType | NetworkType | FindingTypeType


def get_all_types(cls_: type[OOI]) -> Iterator[type[OOI]]:
    yield cls_

    for subclass in cls_.strict_subclasses():
        yield from get_all_types(subclass)


ALL_TYPES: set[type[OOI]] = set(get_all_types(OOI))
T = TypeVar("T", bound=OOI)


@cache
def get_abstract_types() -> set[type[OOI]]:
    abstract_types: set[type[OOI]] = {t for t in ALL_TYPES if t.strict_subclasses()}
    return abstract_types


# Get concrete types (no subclasses)
@cache
def get_concrete_types() -> set[type[OOI]]:
    concrete_types: set[type[OOI]] = {t for t in ALL_TYPES if not t.strict_subclasses()}
    return concrete_types


OOITYPE_BY_NAME: dict[str, type[OOI]] = {t.__name__: t for t in ALL_TYPES}
CONCRETE_OOITYPE_BY_NAME: dict[str, type[OOIType]] = {t.__name__: t for t in get_concrete_types()}


# Collapsed types example
@cache
def get_collapsed_types() -> set[type[OOI]]:
    abstract_ooi_subtypes: set[type[OOI]] = get_abstract_types() - {OOI}

    subclasses_of_abstract_ooi: set[type[OOI]] = set()

    for concrete_type in get_concrete_types():
        for abstract_type in abstract_ooi_subtypes:
            if issubclass(concrete_type, abstract_type):
                subclasses_of_abstract_ooi.add(concrete_type)

    non_abstracted_concrete_types: set[type[OOI]] = get_concrete_types() - subclasses_of_abstract_ooi

    return abstract_ooi_subtypes.union(non_abstracted_concrete_types)


def to_concrete(object_types: set[type[OOI]]) -> set[type[OOI]]:
    concrete_types = set()
    for object_type in object_types:
        if object_type in get_concrete_types():
            concrete_types.add(object_type)
        else:
            child_concrete_types = {t for t in get_concrete_types() if issubclass(t, object_type)}
            concrete_types = concrete_types.union(child_concrete_types)
    return concrete_types


@cache
def type_by_name(type_name: str) -> type[OOI]:
    try:
        return OOITYPE_BY_NAME[type_name]
    except KeyError:
        raise TypeNotFound


@cache
def concrete_type_by_name(type_name: str) -> type[OOI]:
    """Return a concrete subclass of OOI by name (class object)."""
    try:
        return CONCRETE_OOITYPE_BY_NAME[type_name]  # returns type[OOI]
    except KeyError:
        raise TypeNotFound


@cache
def related_object_type(field: FieldInfo) -> type[OOI]:
    object_type: str | type[OOIType] = field.json_schema_extra["object_type"]
    if isinstance(object_type, str):
        return type_by_name(object_type)
    return object_type


def get_relations(object_type: type[OOI]) -> dict[str, type[OOI]]:
    # delegate to cached helper using only strings
    return _cached_relations(object_type.__name__)


@cache
def _cached_relations(cls_name: str) -> dict[str, type[OOI]]:
    cls = OOITYPE_BY_NAME[cls_name]  # reconstruct the class
    return {
        name: related_object_type(field)
        for name, field in cls.model_fields.items()
        if field.annotation == Reference
        or (hasattr(field.annotation, "__args__") and Reference in field.annotation.__args__)
    }


def get_relation(object_type: type[OOI], property_name: str) -> type[OOI]:
    """
    Public API: safely cache relation lookups by using only strings as cache keys.
    """
    cls_name: str = object_type.__name__
    return _cached_relation(cls_name, property_name)


@cache
def _cached_relation(cls_name: str, property_name: str) -> type[OOI]:
    """
    Internal cached function.
    Arguments are fully hashable (str), so MyPy is happy.
    """
    # Resolve the actual class object at runtime
    object_type: type[OOI] = OOITYPE_BY_NAME[cls_name]

    # Compute relations normally
    relations: dict[str, type[OOI]] = get_relations(object_type)
    return relations[property_name]


# FIXME: legacy imports
OOI_TYPES = {ooi_type.get_object_type(): ooi_type for ooi_type in get_concrete_types()}
