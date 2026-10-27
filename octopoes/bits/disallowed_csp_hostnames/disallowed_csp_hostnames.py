from collections.abc import Iterator
from pathlib import Path
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.web import HTTPHeaderHostname

# Vendored from the unmaintained link-shorteners package (MIT, see LICENSE-link-shorteners.txt), which still
# imports pkg_resources and therefore breaks on setuptools >= 82.
with (Path(__file__).parent / "link-shorteners.txt").open(encoding="utf-8") as f:
    LINK_SHORTENERS = frozenset(line.strip().lower() for line in f if line.strip())


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
    disallowed_domains = list(LINK_SHORTENERS) if disallow_url_shorteners else []
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
