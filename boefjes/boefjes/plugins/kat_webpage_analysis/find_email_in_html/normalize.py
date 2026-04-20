from collections.abc import Iterable

import validators
from bs4 import BeautifulSoup

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.email import EmailAddress
from octopoes.models.ooi.network import Network


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    soup = BeautifulSoup(raw, "html.parser")
    mailtos = {a["href"].strip() for a in soup.find_all("a", href=True) if a["href"].lower().startswith("mailto:")}

    network_name = input_ooi["website"]["hostname"]["network"]["name"]
    network_ref = Network(name=network_name).reference
    for mailto in mailtos:
        email = mailto[7:].strip()  # remove "mailto:"
        if not validators.email(email):
            continue

        try:
            localpart, domain = email.lower().split("@", 1)
        except ValueError:
            continue
        domainooi = Hostname(network=network_ref, name=domain.strip())
        yield domainooi
        yield EmailAddress(network=network_ref, localpart=localpart, domain=domainooi.reference)
