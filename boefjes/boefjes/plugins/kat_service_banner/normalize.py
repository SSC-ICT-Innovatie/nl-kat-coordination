import re
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.software import Software, SoftwareInstance

# Only well-anchored, server-speaks-first banner formats are matched, so we
# never fabricate Software from an ambiguous banner. Add patterns here as
# reliable formats are identified.
SSH_BANNER = re.compile(r"^SSH-\d+(?:\.\d+)?-(?P<software>\S+)")
VSFTPD_BANNER = re.compile(r"\(vsFTPd (?P<version>[\w.]+)\)")


def parse_software(banner: str) -> tuple[str, str | None] | None:
    """Return (name, version) for banners we can parse unambiguously, else None."""
    ssh = SSH_BANNER.match(banner)
    if ssh:
        # e.g. "OpenSSH_8.4p1" -> ("OpenSSH", "8.4p1"); "dropbear_2020.81" -> ("dropbear", "2020.81")
        name, _, version = ssh.group("software").partition("_")
        return name, version or None

    vsftpd = VSFTPD_BANNER.search(banner)
    if vsftpd:
        return "vsFTPd", vsftpd.group("version")

    return None


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    """Extract the running Software from a service banner, bound to the IPPort."""
    ip_port = Reference.from_str(input_ooi["primary_key"])
    banner = raw.decode(errors="replace").strip()

    parsed = parse_software(banner)
    if parsed is None:
        return

    name, version = parsed
    software = Software(name=name, version=version)
    yield software
    yield SoftwareInstance(ooi=ip_port, software=software.reference)
