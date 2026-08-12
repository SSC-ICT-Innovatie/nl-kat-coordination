from collections.abc import Iterable

from dns.message import from_text
from dns.rdtypes.ANY.PTR import PTR

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.dns.records import DNSPTRRecord
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.network import Network


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    reference = Reference.from_str(input_ooi["primary_key"])

    answers = raw.decode()
    if answers == "NXDOMAIN" or answers == "NoAnswer":
        return
    if answers.startswith("NoAuthServersReachable:"):
        ft = KATFindingType(id="KAT-LAME-DELEGATION")
        f = Finding(finding_type=ft.reference, ooi=reference, description=answers.split(":", 1)[1])
        yield ft
        yield f
    else:
        lines = [line for line in answers.split("\n") if not line.startswith("option")]
        for rrset in from_text("\n".join(lines[1:])).answer:
            for rr in rrset:
                if isinstance(rr, PTR):
                    value = rrset.to_text()
                    hostname = Hostname(
                        name=rr.to_text().rstrip("."), network=Network(name=input_ooi["network"]["name"]).reference
                    )
                    yield hostname
                    ptr_record = DNSPTRRecord(
                        address=reference, hostname=hostname.reference, value=value, ttl=rrset.ttl
                    )
                    yield ptr_record
