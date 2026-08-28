from nibbles.definitions import NibbleDefinition, NibbleParameter
from octopoes.models import Reference, ScanLevel
from octopoes.models.ooi.dns.records import NXDOMAIN, DNSCAARecord
from octopoes.models.ooi.dns.zone import Hostname


def caa_query(targets: list[Reference | None]) -> str:
    def pull(statements: list[str]) -> str:
        return f"""
            {{
                :query {{
                    :find [(pull ?var [*])] :where [
                        {" ".join(statements)}

                        (or-join [?var ?hostname]
                            [?var :Hostname/primary_key ?hostname]
                            [?var :DNSCAARecord/hostname ?hostname]
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
                    [?mx :DNSCAARecord/primary_key "{str(targets[1])}"]
                    [?mx :DNSCAARecord/hostname ?hostname]
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
                            [?var :DNSCAARecord/primary_key "{str(targets[1])}"]
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
    id="missing-caa",
    signature=[
        NibbleParameter(object_type=Hostname, parser="[*][?object_type == 'Hostname'][]", min_scan_level=ScanLevel.L1),
        NibbleParameter(object_type=DNSCAARecord, parser="[*][?object_type == 'DNSCAARecord'][]", optional=True),
        NibbleParameter(object_type=NXDOMAIN, parser="[*][?object_type == 'NXDOMAIN'][]", optional=True),
    ],
    query=caa_query,
)
