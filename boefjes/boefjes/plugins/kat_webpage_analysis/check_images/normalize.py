from collections.abc import Iterable
from io import BytesIO

from PIL import Image, UnidentifiedImageError
from PIL.ExifTags import TAGS

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.web import ImageMetadata


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    # fetch a reference to the original resource where these headers where downloaded from
    resource = Reference.from_str(input_ooi["primary_key"])
    image = Image.open(BytesIO(raw))
    image.MAX_IMAGE_PIXELS = 7680 * 4320  # 8K pixels for now

    try:
        image_info = {
            "size": image.size,
            "height": image.height,
            "width": image.width,
            "format": image.format,
            "mode": image.mode,
            "is_animated": getattr(image, "is_animated", False),
            "frames": getattr(image, "n_frames", 1),
        }
        exif_data = image.getexif()

        for tag_id in exif_data:
            # human readable tag name
            tag = TAGS.get(tag_id, tag_id)
            tag_data = exif_data.get(tag_id)

            if isinstance(tag_data, bytes):
                tag_data = tag_data.decode()

            image_info[tag] = tag_data

        yield ImageMetadata(resource=resource, image_info=image_info)
    except UnidentifiedImageError:
        kat_number = "BrokenImage"
        kat_ooi = KATFindingType(id=kat_number)
        yield Finding(
            finding_type=kat_ooi.reference,
            ooi=resource,
            description="Image is not recognized, possibly served with broken mime-type.",
        )

    except Image.DecompressionBombWarning:
        kat_number = "DecompressionBomb"
        kat_ooi = KATFindingType(id=kat_number)
        yield Finding(
            finding_type=kat_ooi.reference,
            ooi=resource,
            description=f"Image ended up bigger than {image.MAX_IMAGE_PIXELS} Pixels, possible decompression Bomb",
        )
