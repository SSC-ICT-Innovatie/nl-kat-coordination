from collections.abc import Iterator
from typing import Any

from link_shorteners import link_shorteners_list

from octopoes.models import OOI
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.web import HTTPHeaderHostname

LINK_SHORTENERS = link_shorteners_list()


def get_disallowed_hostnames_from_config(config, config_key, default):
    disallowed_hostnames = config.get(config_key, None)
    if disallowed_hostnames is None:
        return default
    return list(disallowed_hostnames.strip().split(",")) if disallowed_hostnames else []


def run(input_ooi: HTTPHeaderHostname, additional_oois: list, config: dict[str, Any]) -> Iterator[OOI]:
    header_hostname = input_ooi
    header = header_hostname.header

    if header.tokenized.key.lower() != "content-security-policy":
        return

    disallow_url_shorteners = config.get("disallow_url_shorteners", True) if config else True

    hostname = header_hostname.hostname.tokenized.name
    disallowed_domains = link_shorteners_list() if disallow_url_shorteners else []
    disallowed_hostnames_from_config = get_disallowed_hostnames_from_config(config, "disallowed_hostnames", [])

    disallowed_domains.extend(disallowed_hostnames_from_config)
    hostnameparts = hostname.lower().split(".")

    # For e.g. ["www", "example", "com"], check "www.example.com", "example.com" and "com"
    for i in range(len(hostnameparts)):
        if ".".join(hostnameparts[i:]) in disallowed_domains:
            ft = KATFindingType(id="KAT-DISALLOWED-DOMAIN-IN-CSP")
            f = Finding(ooi=input_ooi.reference, finding_type=ft.reference)
            yield ft
            yield f
            break
