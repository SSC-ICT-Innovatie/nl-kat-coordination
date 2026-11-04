"""Pins the internet-nl bit's parameter paths against the models.

The bit aggregates findings from many anchoring objects. When a finding
moves to a new anchor (KAT-HTTPS-NOT-AVAILABLE to the IPAddress,
KAT-SSL-CERT-HOSTNAME-MISMATCH to the chain, #5585 H5), a wrong
relation path silently drops the finding from the aggregation instead
of failing: the framework hydrates what parses and skips the rest. The
only defense is to parse every declared path against the real models —
the same construction the parameter registration performs
(service.py: Path.parse(f"{ooi_type}.{relation_path}").reverse()).
"""

from bits.definitions import get_bit_definitions
from octopoes.models.path import Path


def test_internetnl_parameter_paths_parse():
    bit = get_bit_definitions()["internet-nl"]

    assert bit.consumes.get_object_type() == "Hostname"
    for parameter in bit.parameters:
        path = Path.parse(f"{parameter.ooi_type.get_object_type()}.{parameter.relation_path}").reverse()
        # a path must actually traverse somewhere to be worth declaring
        assert len(path.segments) >= 1


def test_internetnl_covers_the_re_anchored_findings():
    # H5 (#5585): the finding for "HTTPS unavailable" binds to the address,
    # the finding for "name mismatch" binds to the chain. Both must be
    # collectible from the hostname-keyed bit instance.
    bit = get_bit_definitions()["internet-nl"]

    paths = [p.relation_path for p in bit.parameters if p.ooi_type.get_object_type() == "Finding"]
    assert "ooi [is IPAddress]" in paths
    assert "ooi [is TLSCertificateChain].hostname_ip_service.hostname" in paths
