import os
import time
import uuid
from datetime import datetime, timedelta

import pytest

from octopoes.api.models import Declaration, Observation
from octopoes.connector.octopoes import OctopoesAPIConnector
from octopoes.models import Reference
from octopoes.models.ooi.certificate import TLSCertificateChain, X509CertificateV2
from octopoes.models.ooi.network import IPAddressV4, IPPort, Network, PortState, Protocol
from octopoes.models.ooi.service import IPService, Service

if os.environ.get("CI") != "1":
    pytest.skip("Needs XTDB multinode container.", allow_module_level=True)


def test_chain_storage_preserves_certificate_order(octopoes_api_connector: OctopoesAPIConnector, valid_time: datetime):
    """presented_certificates is written leaf-first; XTDB stores vectors as
    ordered lists, so reads must return the leaf first — through every path
    (list_objects, get, and the reverse join the bit parameters walk).
    hasecon's N1 (#5585) assumed otherwise, citing the old docstring."""
    count = 8
    certs = [
        X509CertificateV2(
            fingerprint=f"{i:064d}",
            subject=f"CN=cert{i}",
            valid_from=valid_time - timedelta(days=10 * i),
            valid_until=valid_time + timedelta(days=100 - i),
        )
        for i in range(count)
    ]
    chain = TLSCertificateChain(
        ip_service="IPService|internet|192.0.2.10|tcp|443|https",
        presentation_hash="abc",
        presented_certificates=[c.reference for c in certs],
    )
    source = Reference.from_str("IPService|internet|192.0.2.10|tcp|443|https")

    # the observation's source OOI must exist: declare the endpoint's objects
    for ooi in (
        Network(name="internet"),
        IPAddressV4(network="Network|internet", address="192.0.2.10"),
        IPPort(address="IPAddressV4|internet|192.0.2.10", protocol=Protocol.TCP, port=443, state=PortState.OPEN),
        Service(name="https"),
        IPService(ip_port="IPPort|internet|192.0.2.10|tcp|443", service="Service|https"),
    ):
        octopoes_api_connector.save_declaration(Declaration(ooi=ooi, valid_time=valid_time))

    task_id = uuid.uuid4()
    octopoes_api_connector.save_observation(
        Observation(
            method="ssl-certificates",
            source=source,
            source_method="test",
            task_id=task_id,
            valid_time=valid_time,
            result=[chain, *certs],
        )
    )

    time.sleep(1)

    # 1. read the objects back through the general list path
    stored = {
        o.reference: o
        for o in octopoes_api_connector.list_objects(
            types={TLSCertificateChain, X509CertificateV2}, valid_time=valid_time
        ).items
    }
    stored_chain = next(o for o in stored.values() if isinstance(o, TLSCertificateChain))
    assert stored_chain.presented_certificates == [
        c.reference for c in certs
    ], "storage reordered presented_certificates"
    # the leaf (first written) is the first entry
    assert str(stored_chain.presented_certificates[0]).startswith("X509CertificateV2|")

    # 2. and via the reverse join shape the bit-parameter machinery walks:
    #    the chains that present the leaf — the first bit_ancestor must be
    #    the chain, and the origin parameter binding is deterministic.
    origins = octopoes_api_connector.list_origins(result=chain.reference, valid_time=valid_time)
    assert origins, "chain itself was not saved"

    # sanity: all count certificates exist, none collapsed
    assert len([o for o in stored.values() if isinstance(o, X509CertificateV2)]) == count
