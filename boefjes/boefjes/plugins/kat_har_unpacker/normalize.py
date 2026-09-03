import base64
import binascii
from collections.abc import Iterable

from tanimachi import Har

from boefjes.normalizer_models import NormalizerOutput, NormalizerRawFile
from boefjes.plugins.unpack_common import UnpackGuard, discriminator_tag, normalize_mime_type


def run(input_ooi: dict, raw: bytes | str) -> Iterable[NormalizerOutput]:
    """Explode a HAR file into one raw file per HTTP response body.

    Each extracted body is emitted as a NormalizerRawFile tagged with the response's (bare) mime type
    plus a content-addressed ``har-resource/<hash>`` discriminator, so every raw has a unique mime-type
    set within the parent boefje_meta and Bytes re-dispatches it to the matching content normalizers.
    """
    har = Har.model_validate_json(raw)
    guard = UnpackGuard()

    for entry in har.log.entries:
        if guard.exhausted():
            break

        content = entry.response.content
        if not content.text:
            continue

        if content.encoding == "base64":
            try:
                body = base64.b64decode(content.text)
            except (binascii.Error, ValueError):
                continue
        else:
            body = content.text.encode("utf-8", errors="replace")

        if not body or guard.file_too_large(len(body)):
            continue

        guard.register(len(body))
        yield NormalizerRawFile(
            content=body, mime_types={normalize_mime_type(content.mime_type), discriminator_tag("har-resource", body)}
        )
