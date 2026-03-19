import datetime
import json
from collections.abc import Iterable

from dateutil.parser import parse

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models.ooi.certificate import X509Certificate
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import Network


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    results = json.loads(raw)
    fqdn = input_ooi["hostname"]["name"]
    current = fqdn.lstrip(".")

    network = Network(name="internet")
    network_reference = network.reference

    unique_domains = set()
    for certificate in results:
        common_name = certificate["common_name"].lower().lstrip(".*")

        # walk over all name_value parts (possibly just one, possibly more)
        names = certificate["name_value"].lower().splitlines()
        for name in names:
            if not name.endswith(current):
                # todo: do we want to hint other unrelated hostnames using the same certificate / and this possibly
                #  the same private keys for tls?
                pass
            if name not in unique_domains:
                yield Hostname(name=name, network=network_reference)
                unique_domains.add(name)

        # Yield only current certs.
        expires_in = parse(certificate["not_after"]).astimezone(datetime.timezone.utc) - datetime.datetime.now(
            datetime.timezone.utc
        )
        if expires_in.total_seconds() > 0:
            yield X509Certificate(
                subject=common_name,
                issuer=certificate["issuer_name"],
                valid_from=certificate["not_before"],
                valid_until=certificate["not_after"],
                serial_number=certificate["serial_number"].upper(),
                expires_in=expires_in,
            )
        # walk over the common_name. which might be unrelated to the requested domain, or it might be a parent domain
        # which our dns Boefje should also have picked up.
        # wildcards also trigger here, and won't be visible from a DNS query
        if common_name.endswith(current) or common_name not in unique_domains:
            yield Hostname(name=common_name, network=network_reference)
