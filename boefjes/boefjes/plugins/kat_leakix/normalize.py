import ipaddress
import json
import re
from collections.abc import Iterable
from datetime import datetime, timezone

from dateutil.parser import parse as parse_datetime

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.certificate import (
    SubjectAlternativeNameHostname,
    SubjectAlternativeNameQualifier,
    X509Certificate,
)
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import CVEFindingType, Finding, KATFindingType
from octopoes.models.ooi.network import AutonomousSystem, IPAddressV4, IPAddressV6, IPPort, Network, PortState, Protocol
from octopoes.models.ooi.software import Software, SoftwareInstance

SEVERITY_FINDING_MAPPING = {
    "critical": "KAT-LEAKIX-CRITICAL",
    "high": "KAT-LEAKIX-HIGH",
    "medium": "KAT-LEAKIX-MEDIUM",
    "low": "KAT-LEAKIX-LOW",
    "info": "KAT-LEAKIX-RECOMMENDATION",
}

SEVERITY_LEAKSTAGE_MAPPING = {
    "open": "KAT-LEAKIX-LOW",  # no severity given, default = low
    "explore": "KAT-LEAKIX-HIGH",  # no severity given, default = high
    "exfiltrate": "KAT-LEAKIX-CRITICAL",
}

# Outdated TLS/SSL protocol versions map onto the existing finding types also
# used by the SSL scan boefjes; keys are normalized with normalize_tls_version.
LEGACY_TLS_FINDING_MAPPING = {
    "ssl2": "KAT-SSL-2-SUPPORT",
    "sslv2": "KAT-SSL-2-SUPPORT",
    "ssl3": "KAT-SSL-3-SUPPORT",
    "sslv3": "KAT-SSL-3-SUPPORT",
    "tls1": "KAT-TLS-1.0-SUPPORT",
    "tlsv1": "KAT-TLS-1.0-SUPPORT",
    "tls1.0": "KAT-TLS-1.0-SUPPORT",
    "tlsv1.0": "KAT-TLS-1.0-SUPPORT",
    "tls1.1": "KAT-TLS-1.1-SUPPORT",
    "tlsv1.1": "KAT-TLS-1.1-SUPPORT",
}

# LeakIX event summaries can be large (e.g. a full Apache server-status dump);
# keep the evidence bounded when storing it as Finding.proof.
MAX_PROOF_LENGTH = 2048

# Software names/versions parsed from banners and headers are restricted to a
# conservative charset so banner garbage can never end up in an OOI primary key
# (a "|" in a Software attribute corrupts references downstream).
SOFTWARE_TOKEN_PATTERN = re.compile(r"^([A-Za-z0-9._+-]+)(?:/([A-Za-z0-9._+-]+))?$")
SSH_BANNER_PATTERN = re.compile(r"^SSH-\d+(?:\.\d+)?-(?P<software>[A-Za-z0-9._+-]+)")
LINUX_KERNEL_SUFFIX_PATTERN = re.compile(r"\s+\d+\.\d+\.\d+-\S+$")

# Parenthesized comments in a Server header are only treated as an OS when they
# look like one; anything else ("via 1.2.3.4", mod lists) is ignored.
KNOWN_OS_PREFIXES = (
    "almalinux",
    "centos",
    "debian",
    "fedora",
    "freebsd",
    "gentoo",
    "netbsd",
    "openbsd",
    "red hat",
    "rocky",
    "suse",
    "ubuntu",
    "unix",
    "win",
)

# The Go zero time, which LeakIX emits for fields it did not observe.
GO_ZERO_TIME_PREFIX = "0001-01-01"


def truncate_proof(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    return value if len(value) <= MAX_PROOF_LENGTH else value[:MAX_PROOF_LENGTH] + "…"


def normalize_tls_version(version: str) -> str:
    return version.strip().lower().replace(" ", "").replace("_", "")


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    data = json.loads(raw)

    # Support both old format (list) and new format (dict with metadata)
    if isinstance(data, list):
        # Old format: raw list of events
        results = data
        search_mode = "permissive"
        input_pk = input_ooi["primary_key"]
        components = {}
    else:
        # New format: dict with search_mode, input_ooi, components, and results
        results = data.get("results", [])
        search_mode = data.get("search_mode", "strict")
        input_pk = data.get("input_ooi", input_ooi["primary_key"])
        components = data.get("components", {})

    def enabled(component: str) -> bool:
        # Raw files from before the component toggles existed enable everything
        return components.get(component, True)

    pk_ooi_reference = Reference.from_str(input_ooi["primary_key"])
    network_reference = Network(name="internet").reference

    # Precompute strict-mode filter check outside the loop
    if search_mode == "strict" and input_pk and input_pk.startswith("Hostname|"):
        input_value = input_pk.split("|")[-1]
        strict = bool(input_value)
    else:
        input_value = None
        strict = False

    # LeakIX reports the certificate per event and rescans produce multiple
    # (possibly renewed) certificates for the same endpoint. Only the newest
    # observation per endpoint is emitted, so an old renewed-away certificate
    # cannot raise a false expired-certificate finding.
    certificate_candidates: dict[tuple, tuple[datetime, dict]] = {}

    for event in results:
        # In strict mode, filter hostname results to exact matches only
        if strict:
            event_host = event.get("host", "")
            if event_host.lower() != input_value.lower():
                continue

        # reset loop
        event_ooi_reference = pk_ooi_reference
        ip_port_reference = None

        # Autonomous System. The netblock LeakIX reports alongside it is
        # deliberately not emitted: per-event network attribution is
        # low-confidence (conflicting AS/netblocks for the same IP in one
        # scan), so netblock discovery is left to the specialized boefjes.
        if enabled("asn") and (event.get("network") or {}).get("asn"):
            yield handle_autonomous_system(event)

        if event.get("ip"):
            ip_oois = list(handle_ip(event, network_reference))
            yield from ip_oois
            # handle_ip yields the IPPort last
            ip_port_reference = ip_oois[-1].reference
            event_ooi_reference = ip_port_reference

        if event.get("host"):
            host_ooi = handle_hostname(event, network_reference)
            yield host_ooi
            event_ooi_reference = host_ooi.reference

        primary_software = None
        if enabled("software"):
            software_oois, primary_software, _ = extract_software(event, event_ooi_reference)
            yield from software_oois

        if enabled("ssh"):
            yield from extract_ssh(event, event_ooi_reference)

        if enabled("tls"):
            yield from extract_tls(event, ip_port_reference or event_ooi_reference)

        if enabled("certificates"):
            collect_certificate_candidate(event, certificate_candidates)

        # Leak
        yield from handle_leak(event, event_ooi_reference, primary_software)

        # A CVE is a property of the software version itself, so it binds to the
        # Software OOI. "Which assets are affected" is answered by traversing the
        # graph (Software <- SoftwareInstance <- asset) in reports, which avoids
        # duplicating the same finding per host. Falls back to the asset when no
        # software was detected.
        yield from handle_tag(event, primary_software.reference if primary_software else None, event_ooi_reference)

    for _, event in certificate_candidates.values():
        yield from extract_certificate(event, network_reference)


def handle_autonomous_system(event):
    as_number = str(event["network"]["asn"])
    as_name = event["network"]["organization_name"]
    return AutonomousSystem(number=as_number, name=as_name) if as_name else AutonomousSystem(number=as_number)


def handle_ip(event, network_reference):
    # Store IP
    ip = event["ip"]
    ipvx = ipaddress.ip_address(ip)
    ip_type = IPAddressV4 if ipvx.version == 4 else IPAddressV6

    ip_ooi = ip_type(address=ip, network=network_reference)
    yield ip_ooi

    # Store port (must stay the last OOI yielded; run() takes its reference)
    yield IPPort(
        address=ip_ooi.reference,
        protocol=Protocol("tcp" if event.get("protocol") != "udp" else "udp"),
        port=int(event["port"]),
        state=PortState("open"),
    )


def handle_hostname(event, network_reference):
    try:
        ipvx = ipaddress.ip_address(event["host"])
        if ipvx.version == 4:
            return IPAddressV4(address=event["host"], network=network_reference)
        return IPAddressV6(address=event["host"], network=network_reference)
    except ValueError:
        # Not an IPAddress, so a hostname
        return Hostname(name=event["host"], network=network_reference)


def parse_software_tokens(header_value: str) -> tuple[list[tuple[str, str | None]], list[str]]:
    """Parse a Server/X-Powered-By header value into (name, version) products and OS hints.

    "Apache/2.4.6 (CentOS) OpenSSL/1.0.2k-fips PHP/5.6.40" yields three
    products and the OS hint "CentOS". Tokens that do not match the
    conservative charset are dropped rather than sanitized.
    """
    products = []
    os_hints = []
    # Parenthesized comments first, then whitespace/comma-separated product tokens
    for comment in re.findall(r"\(([^)]*)\)", header_value):
        comment = comment.strip()
        if comment.lower().startswith(KNOWN_OS_PREFIXES):
            os_hints.append(comment)
    for token in re.sub(r"\([^)]*\)", " ", header_value).replace(",", " ").split():
        match = SOFTWARE_TOKEN_PATTERN.match(token)
        if match:
            products.append((match.group(1), match.group(2)))
    return products, os_hints


def clean_os_name(os_name: str) -> str | None:
    """Reduce an OS string like "Debian GNU/Linux 11 (bullseye) 5.4.0-170-generic" to "Debian GNU/Linux 11"."""
    os_name = re.sub(r"\([^)]*\)", " ", os_name)
    os_name = re.sub(r"\s+", " ", os_name).strip()
    os_name = LINUX_KERNEL_SUFFIX_PATTERN.sub("", os_name)
    if not os_name or "|" in os_name:
        return None
    return os_name


def extract_software(event, event_ooi_reference):
    """Extract Software/SoftwareInstance OOIs from service.software (including
    nested modules), the HTTP Server and X-Powered-By headers, and the reported
    operating system. Returns (oois, primary_software, primary_instance)."""
    oois: list = []
    seen: set[tuple] = set()

    def add_software(name, version, instance_parent_reference):
        version = version or None
        # A "|" is the OOI primary-key separator; never let banner/header/service
        # data smuggle one into a Software reference (#5299). Drop a corrupt name
        # outright; keep a clean name but discard a version carrying a pipe.
        if "|" in name:
            return None, None
        if version and "|" in version:
            version = None
        if (name, version) in seen:
            return None, None
        seen.add((name, version))
        software = Software(name=name, version=version)
        instance = SoftwareInstance(ooi=instance_parent_reference, software=software.reference)
        oois.extend([software, instance])
        return software, instance

    service_software = (event.get("service") or {}).get("software") or {}
    software_name = service_software.get("fingerprint") or service_software.get("name")

    primary_software = None
    primary_instance = None
    if software_name:
        primary_software, primary_instance = add_software(
            software_name, service_software.get("version"), event_ooi_reference
        )

    # Modules (e.g. Apache reporting OpenSSL/PHP) nest under the parent instance
    if primary_instance:
        for module in service_software.get("modules") or []:
            if module.get("name"):
                add_software(module["name"], module.get("version"), primary_instance.reference)

    os_names = []
    if service_software.get("os"):
        os_name = clean_os_name(service_software["os"])
        if os_name:
            os_names.append(os_name)

    header = (event.get("http") or {}).get("header") or {}
    for header_value in (header.get("server"), header.get("x-powered-by")):
        if not header_value:
            continue
        products, os_hints = parse_software_tokens(header_value)
        for name, version in products:
            add_software(name, version, event_ooi_reference)
        # Clean header OS hints the same way as service.software["os"] so a
        # parenthesized comment can never carry a pipe into a Software name.
        for os_hint in os_hints:
            cleaned = clean_os_name(os_hint)
            if cleaned:
                os_names.append(cleaned)

    for os_name in os_names:
        add_software(os_name, None, event_ooi_reference)

    return oois, primary_software, primary_instance


def extract_ssh(event, event_ooi_reference):
    """Extract the SSH server Software from the SSH banner (e.g. "SSH-2.0-OpenSSH_9.2p1")."""
    banner = (event.get("ssh") or {}).get("banner") or ""
    match = SSH_BANNER_PATTERN.match(banner.strip())
    if not match:
        return

    # "OpenSSH_9.2p1" -> ("OpenSSH", "9.2p1"); "dropbear_2020.81" -> ("dropbear", "2020.81")
    name, _, version = match.group("software").partition("_")
    software = Software(name=name, version=version or None)
    yield software
    yield SoftwareInstance(ooi=event_ooi_reference, software=software.reference)


def extract_tls(event, target_reference):
    """Report a finding when the service still accepts an outdated TLS/SSL protocol version."""
    ssl_data = event.get("ssl") or {}
    version = ssl_data.get("version")
    if not version:
        return

    finding_id = LEGACY_TLS_FINDING_MAPPING.get(normalize_tls_version(version))
    if not finding_id:
        return

    description = f"The service accepts {version} connections (observed by LeakIX)."
    cypher_suite = ssl_data.get("cypher_suite")
    if cypher_suite:
        description += f" Negotiated cipher suite: {cypher_suite}."

    finding_type = KATFindingType(id=finding_id)
    yield finding_type
    yield Finding(finding_type=finding_type.reference, ooi=target_reference, description=description)


def get_certificate_data(event) -> dict | None:
    certificate_data = (event.get("ssl") or {}).get("certificate") or {}
    # LeakIX emits Go zero values for unobserved certificates: an empty
    # fingerprint and "0001-01-01" validity timestamps. Never build a
    # certificate from those placeholders (it would immediately raise a false
    # expired-certificate finding).
    if not certificate_data.get("fingerprint"):
        return None
    not_before, not_after = certificate_data.get("not_before"), certificate_data.get("not_after")
    if not not_before or not not_after:
        return None
    # Either bound as the Go zero date means LeakIX did not observe it.
    if not_before.startswith(GO_ZERO_TIME_PREFIX) or not_after.startswith(GO_ZERO_TIME_PREFIX):
        return None
    # A validity date that cannot be parsed must skip this certificate, not abort the run.
    try:
        parse_datetime(not_before)
        parse_datetime(not_after)
    except (ValueError, OverflowError, TypeError):
        return None
    return certificate_data


def collect_certificate_candidate(event, candidates: dict) -> None:
    if not get_certificate_data(event):
        return

    try:
        event_time = parse_datetime(event["time"]).astimezone(timezone.utc)
    except (KeyError, TypeError, ValueError, OverflowError):
        event_time = datetime.min.replace(tzinfo=timezone.utc)

    # Key on the host first so distinct SNI virtual hosts on the same IP:port keep
    # their own certificate; rescans of the same host still dedup to the newest.
    key = (event.get("host") or event.get("ip"), str(event.get("port")))
    if key not in candidates or event_time > candidates[key][0]:
        candidates[key] = (event_time, event)


def extract_certificate(event, network_reference):
    """Build the X509Certificate and its SAN hostnames; expiry findings come
    from the existing expiring-certificate bit, SAN hostnames feed asset discovery."""
    certificate_data = get_certificate_data(event)
    if not certificate_data:
        return

    valid_until = certificate_data["not_after"]
    certificate = X509Certificate(
        subject=certificate_data.get("cn") or None,
        issuer=certificate_data.get("issuer_name") or None,
        valid_from=certificate_data["not_before"],
        valid_until=valid_until,
        pk_algorithm=certificate_data.get("key_algo") or None,
        pk_size=certificate_data.get("key_size") or None,
        serial_number=certificate_data["fingerprint"],
        expires_in=parse_datetime(valid_until).astimezone(timezone.utc) - datetime.now(timezone.utc),
    )
    yield certificate

    for san in certificate_data.get("domain") or []:
        if "*" in san:
            yield SubjectAlternativeNameQualifier(name=san, certificate=certificate.reference)
        else:
            hostname = Hostname(name=san, network=network_reference)
            yield hostname
            yield SubjectAlternativeNameHostname(hostname=hostname.reference, certificate=certificate.reference)


def handle_leak(event, event_ooi_reference, software_ooi):
    leak = event.get("leak") or {}
    leak_severity = leak.get("severity")
    # stage is a sibling of dataset in l9format, not a child
    leak_stage = leak.get("stage")
    dataset = leak.get("dataset") or {}
    if leak_severity or leak_stage:
        #  Got the different severities from: https://pkg.go.dev/github.com/LeakIX/l9format#pkg-constants
        leak_infected = dataset.get("infected")
        leak_ransomnote = dataset.get("ransom_notes")

        # new stage or severity, default to low
        kat_finding = "KAT-LEAKIX-LOW"
        if leak_infected or leak_ransomnote:
            kat_finding = "KAT-LEAKIX-CRITICAL"
        elif leak_severity in SEVERITY_FINDING_MAPPING:
            kat_finding = SEVERITY_FINDING_MAPPING[leak_severity]
        elif leak_stage in SEVERITY_LEAKSTAGE_MAPPING:
            kat_finding = SEVERITY_LEAKSTAGE_MAPPING[leak_stage]

        finding_type = KATFindingType(id=kat_finding)
        yield finding_type

        kat_info = []
        # event_source is the LeakIX plugin that made the detection, i.e. what
        # kind of leak this is. The old code labelled this "Plugin" but
        # interpolated the OOI reference instead of the plugin name.
        event_source = event.get("event_source")
        if software_ooi:
            kat_info.append(f'Software = "{software_ooi.name}".')
        elif event_source:
            kat_info.append(f'Plugin = "{event_source}".')

        if leak.get("type"):
            kat_info.append(f"Leak type: {leak['type']}.")

        if leak_infected:
            kat_info.append("Found evidence of external activity.")
        if leak_ransomnote:
            kat_info.append("Found a ransom note.")
        if leak_stage:
            kat_info.append(f"Stage of the leak is: {leak_stage}.")

        # Scale of the exposure.
        for field in ("rows", "files", "size", "collections"):
            value = dataset.get(field)
            if value:
                kat_info.append(f"{field.capitalize()}: {value}.")

        # An unauthenticated service exposing data is worth calling out explicitly.
        if ((event.get("service") or {}).get("credentials") or {}).get("noauth"):
            kat_info.append("No authentication required.")

        if event.get("time"):
            kat_info.append(f"First seen: {event['time'][:19]}.")

        # The finding binds to the scanned asset (hostname, IP port), not to the
        # detected Software: a leak is a property of the host, and the software
        # relation already exists through the SoftwareInstance (#3211).
        yield Finding(
            finding_type=finding_type.reference,
            ooi=event_ooi_reference,
            description=", ".join(kat_info),
            proof=truncate_proof(event.get("summary")),
        )


def handle_tag(event, software_reference=None, event_ooi_reference=None):
    # Tags (CVE's) bind to the Software OOI; the scanned asset is the fallback.
    if isinstance(event.get("tags"), Iterable):
        for tag in event.get("tags", {}):
            if re.match(r"cve-\d{4}-\d{4,6}", tag):
                ft = CVEFindingType(id=tag)
                cve_ooi = software_reference if software_reference else event_ooi_reference
                f = Finding(finding_type=ft.reference, ooi=cve_ooi)
                yield ft
                yield f
