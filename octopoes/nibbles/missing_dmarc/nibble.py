from nibbles.definitions import NibbleDefinition, NibbleParameter
from octopoes.models import Reference, ScanLevel
from octopoes.models.ooi.dns.records import NXDOMAIN
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.email_security import DMARCTXTRecord


def dmarc_query(targets: list[Reference | None]) -> str:
    def pull(statements: list[str]) -> str:
        return f"""
            {{
                :query {{
                    :find [(pull ?var [*])] :where [
                        {" ".join(statements)}

                        (or-join [?var ?hostname]
                            [?var :Hostname/primary_key ?hostname]
                            [?var :DMARCTXTRecord/hostname ?hostname]
                            [?var :NXDOMAIN/hostname ?hostname]
                        )
                    ]
                }}
            }}
        """

    sgn = "".join(str(int(isinstance(target, Reference))) for target in targets)
    if sgn == "100":
        return pull(
            [
                f"""
                    [?hostname :Hostname/primary_key "{str(targets[0])}"]
                """
            ]
        )
    elif sgn == "010":
        return pull(
            [
                f"""
                    [?mx :DMARCTXTRecord/primary_key "{str(targets[1])}"]
                    [?mx :DMARCTXTRecord/hostname ?hostname]
                """
            ]
        )
    elif sgn == "001":
        return pull(
            [
                f"""
                    [?nx :NXDOMAIN/primary_key "{str(targets[2])}"]
                    [?nx :NXDOMAIN/hostname ?hostname]
                """
            ]
        )
    elif sgn == "111":
        return f"""
            {{
                :query {{
                    :find [(pull ?var [*])] :where [
                        (or-join [?var]
                            [?var :Hostname/primary_key "{str(targets[0])}"]
                            [?var :DMARCTXTRecord/primary_key "{str(targets[1])}"]
                            [?var :NXDOMAIN/primary_key "{str(targets[2])}"]
                        )
                    ]
                 }}
            }}
        """
    else:
        return pull(
            [
                """
                    [?hostname :Hostname/object_type "Hostname"]
                """
            ]
        )


NIBBLE = NibbleDefinition(
    id="missing-dmarc",
    signature=[
        NibbleParameter(object_type=Hostname, parser="[*][?object_type == 'Hostname'][]", min_scan_level=ScanLevel.L1),
        NibbleParameter(object_type=DMARCTXTRecord, parser="[*][?object_type == 'DMARCTXTRecord'][]", optional=True),
        NibbleParameter(object_type=NXDOMAIN, parser="[*][?object_type == 'NXDOMAIN'][]", optional=True),
    ],
    query=dmarc_query,
)
