"""Pins what the ssl-certificates normalizer consumes.

H4 (#5585): every raw also carries the default boefje/<id> mime, and
Mula schedules a normalizer on any matching mime. Consuming
boefje/ssl-certificates meant info/boefje outcomes (no TLS observed)
scheduled this normalizer, which yielded nothing — and the empty
observation deleted the endpoint's chain, SANs and findings. Only the
presentation mime may be consumed: error/* raws are skipped by the
scheduler and info/boefje matches no normalizer.
"""

import json
from pathlib import Path

DEFINITION = Path(__file__).parent.parent.parent / "boefjes" / "plugins" / "kat_ssl_certificates" / "normalizer.json"


def test_normalizer_consumes_only_the_presentation_mime():
    consumes = json.loads(DEFINITION.read_text())["consumes"]

    assert "openkat/ssl-certificates-output" in consumes
    assert "boefje/ssl-certificates" not in consumes
