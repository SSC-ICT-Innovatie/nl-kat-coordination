import ipaddress
import json
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, IPPort, Network, PortState, Protocol


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    results = json.loads(raw)
    pk_ooi = Reference.from_str(input_ooi["primary_key"])
    network = Network(name="internet").reference

    # Structure based on https://docs.binaryedge.io/modules/<accepted_modules_name>/
    accepted_modules = ("ssl-simple", "sslv2", "jarm")
    for scan in results["results"]:
        module = scan["origin"]["type"]
        if module not in accepted_modules:
            continue

        port_nr = int(scan["target"]["port"])
        protocol = scan["target"]["protocol"]
        ip = scan["target"]["ip"]

        if input_ooi["object_type"] in ["IPAddressV4", "IPAddressV6"]:
            ip_ref = pk_ooi
        else:
            ipvx = ipaddress.ip_address(ip)
            if ipvx.version == 4:
                ip_ooi = IPAddressV4(address=ip, network=network)
            else:
                ip_ooi = IPAddressV6(address=ip, network=network)
            yield ip_ooi
            ip_ref = ip_ooi.reference

        ip_port_ooi = IPPort(address=ip_ref, protocol=Protocol(protocol), port=port_nr, state=PortState("open"))
        yield ip_port_ooi

        # TODO: result.data.server_info {openssl_cipher_string_supported,highest_ssl_version_supported,ja3,ja3_digest}
        # TODO: version
        # TODO: jarm
        for cert_chain in scan.get("data", {}).get("cert_info", {}).get("certificate_chain", []):
            pass

        vulns = scan.get("data", {}).get("vulnerabilities", {})
        if vulns.get("compression", {}).get("supports_compression"):
            kat_ooi = KATFindingType(id="KAT-VERIFIED-VULNERABILITY")
            yield kat_ooi
            yield Finding(
                finding_type=kat_ooi.reference,
                ooi=ip_port_ooi.reference,
                description="SSL is set to support compression, but it is advised to disable this.",
            )
        if vulns.get("fallback", {}).get("supports_fallback_scsv"):
            kat_ooi = KATFindingType(id="KAT-VERIFIED-VULNERABILITY")
            yield kat_ooi
            yield Finding(
                finding_type=kat_ooi.reference,
                ooi=ip_port_ooi.reference,
                description="SSL is set to support fallback scsv, but it is advised to disable this.",
            )
        if "heartbleed" in vulns and vulns["heartbleed"]["is_vulnerable_to_heartbleed"]:
            kat_ooi = KATFindingType(id="KAT-VERIFIED-VULNERABILITY")
            yield kat_ooi
            yield Finding(
                finding_type=kat_ooi.reference,
                ooi=ip_port_ooi.reference,
                description="It is confirmed this connection is vulnerable to Heartbleed, it is advised to adopt "
                "the fix.",
            )
        if "openssl_ccs" in vulns and vulns["openssl_ccs"]["is_vulnerable_to_ccs_injection"]:
            kat_ooi = KATFindingType(id="KAT-VERIFIED-VULNERABILITY")
            yield kat_ooi
            yield Finding(
                finding_type=kat_ooi.reference,
                ooi=ip_port_ooi.reference,
                description="It is verified this connection is vulnerable to the OpenSSL CSS Injection Vulnerability.",
            )
        if "renegotiation" in vulns and vulns["renegotiation"]["accepts_client_renegotiation"]:
            kat_ooi = KATFindingType(id="KAT-VERIFIED-VULNERABILITY")
            yield kat_ooi
            yield Finding(
                finding_type=kat_ooi.reference,
                ooi=ip_port_ooi.reference,
                description="This SSL accepts client renegotiation, but i can be used in a DOS attack.",
            )
        if "renegotiation" in vulns and vulns["renegotiation"]["supports_secure_renegotiation"]:
            kat_ooi = KATFindingType(id="KAT-VERIFIED-VULNERABILITY")
            yield kat_ooi
            yield Finding(
                finding_type=kat_ooi.reference,
                ooi=ip_port_ooi.reference,
                description="This SSL accepts secure renegotiation, but i can be used in a DOS attack.",
            )
        if "robot_result_enum" in vulns.get("robot", {}):
            robot = vulns["robot"]["robot_result_enum"]
            if robot in (
                "VULNERABLE_WEAK_ORACLE",  # the server is vulnerable but the attack would take too long
                "VULNERABLE_STRONG_ORACLE",  # the server is vulnerable and real attacks are feasible
                "NOT_VULNERABLE_NO_ORACLE",  # the server supports RSA cipher suites but does not act as an oracle
                "NOT_VULNERABLE_RSA_NOT_SUPPORTED",  # the server does not supports RSA cipher suites
                "UNKNOWN_INCONSISTENT_RESULTS",  # could not determine whether the server is vulnerable or not
            ):
                pass  # todo
