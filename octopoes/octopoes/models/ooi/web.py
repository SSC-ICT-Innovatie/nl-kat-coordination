from enum import Enum
from typing import Literal

from pydantic import AnyUrl

from octopoes.models import OOI, PrimaryKeyToken, Reference
from octopoes.models.ooi.certificate import X509Certificate
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddress, Network
from octopoes.models.ooi.service import IPService
from octopoes.models.persistence import ReferenceField


def format_web_url_token(token: PrimaryKeyToken) -> str:
    port = f":{token.port}" if token.port else ""
    try:
        netloc = token.netloc.address
    except KeyError:
        netloc = token.netloc.name

    return f"{token.scheme}://{netloc}{port}{token.path}"


class Website(OOI):
    object_type: Literal["Website"] = "Website"

    ip_service: Reference = ReferenceField(IPService, max_issue_scan_level=0, max_inherit_scan_level=4)
    hostname: Reference = ReferenceField(Hostname, max_inherit_scan_level=4)
    certificate: Reference | None = ReferenceField(X509Certificate, default=None, max_issue_scan_level=1)

    _natural_key_attrs = ["ip_service", "hostname"]

    _reverse_relation_names = {"ip_service": "websites", "hostname": "websites"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        t = reference.tokenized
        service = t.ip_service.service.name
        address = t.ip_service.ip_port.address.address
        port = t.ip_service.ip_port.port
        return f"{service}://{t.hostname.name}:{port} @ {address}"


class WebScheme(Enum):
    HTTP = "http"
    HTTPS = "https"


class WebURL(OOI):
    network: Reference = ReferenceField(Network)

    scheme: WebScheme
    port: int
    path: str


class HostnameHTTPURL(WebURL):
    object_type: Literal["HostnameHTTPURL"] = "HostnameHTTPURL"

    netloc: Reference = ReferenceField(Hostname, max_issue_scan_level=2, max_inherit_scan_level=4)

    _natural_key_attrs = ["scheme", "netloc", "port", "path"]
    _reverse_relation_names = {"netloc": "urls"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        tokenized = reference.tokenized
        port = f":{tokenized.port}" if tokenized.port else ""
        return f"{tokenized.scheme}://{tokenized.netloc.name}{port}{tokenized.path}"


class IPAddressHTTPURL(WebURL):
    object_type: Literal["IPAddressHTTPURL"] = "IPAddressHTTPURL"

    netloc: Reference = ReferenceField(IPAddress, max_issue_scan_level=1, max_inherit_scan_level=4)

    _natural_key_attrs = ["scheme", "netloc", "port", "path"]
    _reverse_relation_names = {"netloc": "urls"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        tokenized = reference.tokenized
        port = f":{tokenized.port}" if tokenized.port else ""
        return f"{tokenized.scheme}://{tokenized.netloc.address}{port}{tokenized.path}"


class HTTPResource(OOI):
    object_type: Literal["HTTPResource"] = "HTTPResource"

    website: Reference = ReferenceField(Website, max_issue_scan_level=0, max_inherit_scan_level=4)
    web_url: Reference = ReferenceField(WebURL, max_issue_scan_level=1, max_inherit_scan_level=4)
    redirects_to: Reference | None = ReferenceField(WebURL, default=None)

    _natural_key_attrs = ["website", "web_url"]

    _reverse_relation_names = {"website": "resources", "web_url": "resources"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        t = reference.tokenized
        port = f":{t.web_url.port}"
        try:
            netloc = t.web_url.netloc.address
        except KeyError:
            netloc = t.web_url.netloc.name

        web_url = f"{t.web_url.scheme}://{netloc}{port}{t.web_url.path}"
        address = t.website.ip_service.ip_port.address.address

        return f"{web_url} @ {address}"


class HTTPHeader(OOI):
    object_type: Literal["HTTPHeader"] = "HTTPHeader"

    resource: Reference = ReferenceField(HTTPResource, max_issue_scan_level=0, max_inherit_scan_level=4)
    key: str
    value: str

    _natural_key_attrs = ["resource", "key"]
    _information_value = ["key"]
    _reverse_relation_names = {"url": "http_headers"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        t = reference.tokenized

        port = f":{t.resource.web_url.port}" if t.resource.web_url.port else ""
        try:
            netloc = t.resource.web_url.netloc.address
        except KeyError:
            netloc = t.resource.web_url.netloc.name

        web_url = f"{t.resource.web_url.scheme}://{netloc}{port}{t.resource.web_url.path}"
        address = t.resource.website.ip_service.ip_port.address.address

        return f"{reference.tokenized.key} @ {web_url} @ {address}"


class URL(OOI):
    object_type: Literal["URL"] = "URL"

    network: Reference = ReferenceField(Network)
    raw: AnyUrl

    web_url: Reference | None = ReferenceField(WebURL, max_issue_scan_level=2, default=None)

    _natural_key_attrs = ["network", "raw"]

    _reverse_relation_names = {"network": "urls"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"{reference.tokenized.raw} @{reference.tokenized.network.name}"


class HTTPHeaderURL(OOI):
    object_type: Literal["HTTPHeaderURL"] = "HTTPHeaderURL"

    header: Reference = ReferenceField(HTTPHeader, max_issue_scan_level=0, max_inherit_scan_level=1)
    url: Reference = ReferenceField(URL, max_issue_scan_level=1, max_inherit_scan_level=0)

    _natural_key_attrs = ["header", "url"]
    _reverse_relation_names = {"header": "urls", "url": "headers_containing_url"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        t = reference.tokenized.header

        port = f":{t.resource.web_url.port}" if t.resource.web_url.port else ""
        try:
            netloc = t.resource.web_url.netloc.address
        except KeyError:
            netloc = t.resource.web_url.netloc.name

        web_url = f"{t.resource.web_url.scheme}://{netloc}{port}{t.resource.web_url.path}"
        address = t.resource.website.ip_service.ip_port.address.address

        return f"{t.key} @ {web_url} @ {address} contains {str(reference.tokenized.url.raw)}"


class HTTPHeaderHostname(OOI):
    object_type: Literal["HTTPHeaderHostname"] = "HTTPHeaderHostname"

    header: Reference = ReferenceField(HTTPHeader, max_issue_scan_level=0, max_inherit_scan_level=1)
    hostname: Reference = ReferenceField(Hostname, max_issue_scan_level=1, max_inherit_scan_level=0)

    _natural_key_attrs = ["header", "hostname"]
    _reverse_relation_names = {"header": "hostnames", "hostname": "headers_containing_hostname"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        t = reference.tokenized.header

        port = f":{t.resource.web_url.port}" if t.resource.web_url.port else ""
        try:
            netloc = t.resource.web_url.netloc.address
        except KeyError:
            netloc = t.resource.web_url.netloc.name

        web_url = f"{t.resource.web_url.scheme}://{netloc}{port}{t.resource.web_url.path}"
        address = t.resource.website.ip_service.ip_port.address.address

        return f"{t.key} @ {web_url} @ {address} contains {str(reference.tokenized.hostname.name)}"


class ImageMetadata(OOI):
    object_type: Literal["ImageMetadata"] = "ImageMetadata"

    resource: Reference = ReferenceField(HTTPResource, max_issue_scan_level=0, max_inherit_scan_level=4)
    image_info: dict

    _natural_key_attrs = ["resource"]
    _reverse_relation_names = {"resource": "ImageMetaData"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        try:
            t = reference.tokenized

            port = f":{t.resource.web_url.port}" if t.resource.web_url.port else ""
            try:
                netloc = t.resource.web_url.netloc.address
            except KeyError:
                netloc = t.resource.web_url.netloc.name

            web_url = f"{t.resource.web_url.scheme}://{netloc}{port}{t.resource.web_url.path}"
            address = t.resource.website.ip_service.ip_port.address.address

            return f"{web_url} @ {address}"
        except IndexError:
            # try parsing reference as a HostnameHTTPURL instead
            tokenized = HostnameHTTPURL.get_tokenized_primary_key(reference.natural_key)
            port = f":{tokenized.port}" if tokenized.port else ""
            return f"{tokenized.scheme}://{tokenized.netloc.name}{port}{tokenized.path}"


class RESTAPI(OOI):
    object_type: Literal["RESTAPI"] = "RESTAPI"

    api_url: Reference = ReferenceField(WebURL)

    _natural_key_attrs = ["api_url"]
    _reverse_relation_names = {"api_url": "api_url_of"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return format_web_url_token(reference.tokenized.api_url)


class APIDesignRule(OOI):
    object_type: Literal["APIDesignRule"] = "APIDesignRule"

    name: str

    _natural_key_attrs = ["name"]
    _reverse_relation_names = {}
    _traversable = False

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return reference.tokenized.name


class APIDesignRuleResult(OOI):
    object_type: Literal["APIDesignRuleResult"] = "APIDesignRuleResult"

    rest_api: Reference = ReferenceField(RESTAPI)
    rule: Reference = ReferenceField(APIDesignRule)
    passed: bool
    message: str

    _natural_key_attrs = ["rest_api", "rule"]
    _reverse_relation_names = {"rest_api": "api_design_rule_results", "rule": "results"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        t = reference.tokenized

        rule = t.rule.name
        api_url = format_web_url_token(t.rest_api.api_url)

        return f"{rule} @ {api_url}"


class SecurityTXT(OOI):
    object_type: Literal["SecurityTXT"] = "SecurityTXT"

    website: Reference = ReferenceField("Website", max_issue_scan_level=0, max_inherit_scan_level=4)
    url: Reference = ReferenceField("URL", max_issue_scan_level=0, max_inherit_scan_level=4)

    redirects_to: Reference | None = ReferenceField(
        "SecurityTXT", max_issue_scan_level=2, max_inherit_scan_level=0, default=None
    )
    security_txt: str | None = None

    _natural_key_attrs = ["website", "url"]
    _reverse_relation_names = {
        "website": "security_txt_of",
        "url": "security_txt",
        "redirects_to": "is_being_redirected_to_by",
    }
