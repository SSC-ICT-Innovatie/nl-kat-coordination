from collections.abc import Iterable
from urllib.parse import urljoin

import validators
from bs4 import BeautifulSoup

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models.ooi.network import Network
from octopoes.models.ooi.web import URL


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    soup = BeautifulSoup(raw, "html.parser")
    images = {img["src"] for img in soup.find_all("img", src=True)}

    network_name = input_ooi["website"]["hostname"]["network"]["name"]
    host = input_ooi["website"]["hostname"]["name"]
    service = input_ooi["website"]["ip_service"]["service"]["name"]

    url = f"{service}://{host}/"

    for img in images:
        if not validators.url(img):
            img = urljoin(url, img)

        yield URL(network=Network(name=network_name).reference, raw=img)
