import json
import logging

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# CPE target_sw values that map to a Snyk ecosystem prefix.
# If the Software OOI has a CPE, we derive the ecosystem from its target_sw
# field. npm is the fallback when no CPE is available or target_sw is "*".
_CPE_TARGET_SW_TO_SNYYK_ECOSYSTEM = {
    "node.js": "npm",
    "nodejs": "npm",
    "python": "pip",
    "java": "maven",
    "ruby": "rubygems",
    "go": "go",
    "php": "composer",
    "rust": "cargo",
    "dotnet": "nuget",
    "c#": "nuget",
}


def _ecosystem_from_cpe(cpe: str | None) -> str:
    """Derive the Snyk ecosystem prefix from a CPE's target_sw field."""
    if not cpe:
        return "npm"
    parts = cpe.split(":")
    # cpe:2.3:a:vendor:product:version:update:edition:language:sw_edition:target_sw:target_hw:other
    if len(parts) >= 11:
        target_sw = parts[10].lower()
        return _CPE_TARGET_SW_TO_SNYYK_ECOSYSTEM.get(target_sw, "npm")
    return "npm"


def _parse_nuxt_data(html: str) -> dict:
    """Extract and resolve the __NUXT_DATA__ JSON payload from a snyk.io page.

    Nuxt serialises SSR state as a flat array where integer values in
    objects/arrays are references to other indices. We resolve those into
    a normal nested structure.
    """
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NUXT_DATA__")
    if script is None:
        raise ValueError("No __NUXT_DATA__ script tag found on snyk.io page")

    data = json.loads(script.string)

    def resolve(idx: int, seen: set[int] | None = None) -> object:
        if seen is None:
            seen = set()
        if idx in seen:
            return None  # circular reference guard
        seen = seen | {idx}
        val = data[idx]
        if isinstance(val, list):
            # Nuxt wraps reactive objects as ["ShallowReactive", ref]
            if len(val) == 2 and val[0] in ("ShallowReactive", "ShallowRef", "ShallowReadonly"):
                return resolve(val[1], seen)
            return [resolve(item, seen) if isinstance(item, int) else item for item in val]
        if isinstance(val, dict):
            return {k: resolve(v, seen) if isinstance(v, int) else v for k, v in val.items()}
        return val

    # The root is at index 1: {data: 2, state: ..., ...}
    root = resolve(1)
    if not isinstance(root, dict):
        raise ValueError("Unexpected __NUXT_DATA__ root structure")
    data_obj = root.get("data")
    if isinstance(data_obj, dict):
        # The package data is under the "package-data" key (or similar)
        # The exact key name is a hash, so we look for the key that has
        # "vulnerabilities" and "versions" in its resolved value.
        for value in data_obj.values():
            if isinstance(value, dict) and "vulnerabilities" in value and "versions" in value:
                return value
    raise ValueError("Could not locate package data in __NUXT_DATA__ payload")


def _affected_versions_to_string(ranges: list[dict]) -> str:
    """Convert Nuxt affectedVersions structure to a check_version_in-compatible string."""
    parts = []
    for r in ranges:
        min_v = r.get("min")
        max_v = r.get("max")
        if min_v and max_v:
            min_str = f">={min_v['version']}" if min_v.get("inclusive") else f">{min_v['version']}"
            max_str = f"<={max_v['version']}" if max_v.get("inclusive") else f"<{max_v['version']}"
            parts.append(f"{min_str},{max_str}")
        elif max_v:
            max_str = f"<={max_v['version']}" if max_v.get("inclusive") else f"<{max_v['version']}"
            parts.append(max_str)
        elif min_v:
            min_str = f">={min_v['version']}" if min_v.get("inclusive") else f">{min_v['version']}"
            parts.append(min_str)
    return ",".join(parts)


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ = boefje_meta["arguments"]["input"]
    software_name = input_["name"]
    cpe = input_.get("cpe")

    ecosystem = _ecosystem_from_cpe(cpe)
    url_snyk = f"https://snyk.io/vuln/{ecosystem}:{software_name.lower().replace(' ', '-')}"
    page = requests.get(url_snyk, timeout=30)

    try:
        pkg = _parse_nuxt_data(page.text)
    except ValueError:
        logger.warning("Could not parse snyk.io page for %s", software_name)
        return [(set(), json.dumps({"vulnerabilities": [], "latest_version": None}))]

    vulnerabilities = []
    for vuln in pkg.get("vulnerabilities", []):
        cve_ids = vuln.get("identifiers", {}).get("CVE", [])
        cve = cve_ids[0] if cve_ids else None
        affected = _affected_versions_to_string(vuln.get("affectedVersions", []))
        vulnerabilities.append(
            {
                "id": vuln["id"],
                "title": vuln["title"],
                "severity": vuln.get("severity"),
                "cvss_score": vuln.get("cvssScore"),
                "affected_versions": affected,
                "cve": cve,
            }
        )

    # Find latest version
    latest_version = None
    latest_info = pkg.get("latestReleaseVersion")
    if isinstance(latest_info, dict):
        latest_version = latest_info.get("version")
    elif isinstance(latest_info, str):
        latest_version = latest_info

    result = {"vulnerabilities": vulnerabilities, "latest_version": latest_version}
    return [(set(), json.dumps(result))]
