"""
CVE-2024-6387 checker
Author: Mischa van Geelen <@rickgeex>

"""

from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import CVEFindingType, Finding
from packaging.version import Version

VULNERABLE_VERSIONS = [
    "SSH-2.0-OpenSSH_8.5",
    "SSH-2.0-OpenSSH_8.6",
    "SSH-2.0-OpenSSH_8.7",
    "SSH-2.0-OpenSSH_8.8",
    "SSH-2.0-OpenSSH_8.9",
    "SSH-2.0-OpenSSH_9.0",
    "SSH-2.0-OpenSSH_9.1",
    "SSH-2.0-OpenSSH_9.2",
    "SSH-2.0-OpenSSH_9.3",
    "SSH-2.0-OpenSSH_9.4",
    "SSH-2.0-OpenSSH_9.5",
    "SSH-2.0-OpenSSH_9.6",
    "SSH-2.0-OpenSSH_9.7",
]


def is_vulnerable(banner: str) -> bool:
    if not any(version in banner for version in VULNERABLE_VERSIONS):
        return False

    if banner.startswith("SSH-2.0-OpenSSH_9.2p1 Debian-2+deb12u"):
        _, security_update = banner.split("deb12u")
        if Version(security_update) >= Version("3"):
            return False
    elif banner.startswith("SSH-2.0-OpenSSH_9.6p1 Ubuntu-3ubuntu"):
        _, security_update = banner.split("3ubuntu")
        if Version(security_update) >= Version("13.3"):
            return False
    elif banner.startswith("SSH-2.0-OpenSSH_9.3p1 Ubuntu-1ubuntu"):
        _, security_update = banner.split("1ubuntu")
        if Version(security_update) >= Version("3.6"):
            return False
    elif banner.startswith("SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu"):
        _, security_update = banner.split("3ubuntu")
        if Version(security_update) >= Version("0.10"):
            return False

    return True


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    ooi = Reference.from_str(input_ooi["primary_key"])

    banner = raw.decode()

    if banner.startswith("SSH-2.0-OpenSSH") and is_vulnerable(banner):
        finding_type = CVEFindingType(id="CVE-2024-6387")
        finding = Finding(
            finding_type=finding_type.reference,
            ooi=ooi,
            description="Service is most likely vulnerable to CVE-2024-6387",
        )
        yield finding_type
        yield finding
