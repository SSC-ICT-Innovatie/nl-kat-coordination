from __future__ import annotations

from collections.abc import Iterator

import yaml
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

OOIType = ConcreteOOIType | NetworkType | FindingTypeType


def get_all_types(cls_: type[OOI]) -> Iterator[type[OOI]]:
    yield cls_

    for subclass in cls_.strict_subclasses():
        yield from get_all_types(subclass)


ALL_TYPES = set(get_all_types(OOI))


def get_abstract_types() -> set[type[OOI]]:
    return {t for t in ALL_TYPES if t.strict_subclasses()}


def get_concrete_types() -> set[type[OOI]]:
    return {t for t in ALL_TYPES if not t.strict_subclasses()}


def get_collapsed_types() -> set[type[OOI]]:
    abstract_ooi_subtypes = get_abstract_types() - {OOI}

    subclasses_of_abstract_ooi: set[type[OOI]] = set()

    for concrete_type in get_concrete_types():
        for abstract_type in abstract_ooi_subtypes:
            if issubclass(concrete_type, abstract_type):
                subclasses_of_abstract_ooi.add(concrete_type)

    non_abstracted_concrete_types = get_concrete_types() - subclasses_of_abstract_ooi

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


def type_by_name(type_name: str) -> type[OOI]:
    try:
        return next(t for t in ALL_TYPES if t.__name__ == type_name)
    except StopIteration:
        raise TypeNotFound


def related_object_type(field: FieldInfo) -> type[OOI]:
    object_type: str | type[OOI] = field.json_schema_extra["object_type"]
    if isinstance(object_type, str):
        return type_by_name(object_type)
    return object_type


def get_relations(object_type: type[OOI]) -> dict[str, type[OOI]]:
    return {
        name: related_object_type(field)
        for name, field in object_type.model_fields.items()
        if field.annotation == Reference
        or (hasattr(field.annotation, "__args__") and Reference in field.annotation.__args__)
    }


def get_relation(object_type: type[OOI], property_name: str) -> type[OOI]:
    return get_relations(object_type)[property_name]


# FIXME: legacy imports
OOI_TYPES = {ooi_type.get_object_type(): ooi_type for ooi_type in get_concrete_types()}

# yaml.representer.SafeRepresenter.ignore_aliases = lambda *data : True

for ooi_cls in ALL_TYPES:
    if hasattr(ooi_cls, "yml_representer"):
        yaml.SafeDumper.add_representer(ooi_cls, ooi_cls.yml_representer)
    yaml.SafeLoader.add_constructor("!" + ooi_cls.__name__, ooi_cls.yml_constructor)
