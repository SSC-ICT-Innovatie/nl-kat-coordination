import csv
import io
import logging
from collections.abc import Iterable
from ipaddress import IPv4Network, ip_network

from pydantic import ValidationError

from boefjes.normalizer_models import NormalizerDeclaration, NormalizerOutput
from octopoes.models import OOI, Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, Network
from octopoes.models.ooi.web import URL
from octopoes.models.types import OOIType

OOI_TYPES: dict[str, dict] = {
    "Hostname": {"type": Hostname},
    "URL": {"type": URL},
    "Network": {"type": Network, "default": "internet", "argument": "name"},
    "IPAddressV4": {"type": IPAddressV4},
    "IPAddressV6": {"type": IPAddressV6},
}

logger = logging.getLogger(__name__)


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    reference_cache = {"Network": {"internet": Network(name="internet")}}

    yield from process_csv(raw, reference_cache)


def process_csv(csv_raw_data: bytes, reference_cache: dict) -> Iterable[NormalizerOutput]:
    csv_data = io.StringIO(csv_raw_data.decode("UTF-8"))

    object_type = get_object_type(csv_data)

    for row_number, row in enumerate(csv.DictReader(csv_data, delimiter=",", quotechar='"')):
        if not row:
            continue  # skip empty lines

        try:
            ooi, extra_declarations = get_ooi_from_csv(object_type, row, reference_cache)

            yield from extra_declarations

            yield NormalizerDeclaration(ooi=ooi)
        except ValidationError:
            logger.exception("Validation failed for row %s", row)


def get_object_type(csv_data: io.StringIO) -> str:
    csv_data.seek(0)
    headers = csv_data.readline()
    line = csv_data.readline()
    csv_data.seek(0)

    if "name" in headers:
        return "Hostname"

    if "raw" in headers:
        return "URL"

    if "address" in headers:
        if line:
            address = next(csv.DictReader(csv_data, delimiter=",", quotechar='"'))["address"]
            csv_data.seek(0)

            return "IPAddressV4" if isinstance(ip_network(address), IPv4Network) else "IPAddressV6"

        return "IPAddressV4"  # No data in the csv, so this is redundant but an Exception would be overkill.

    raise ValueError("Unsupported OOI type for csv normalizer.")


def get_ooi_from_csv(
    ooi_type_name: str, values: dict[str, str], reference_cache: dict
) -> tuple[OOIType, list[NormalizerDeclaration]]:
    skip_properties = ("object_type", "scan_profile", "primary_key")

    ooi_type = OOI_TYPES[ooi_type_name]["type"]
    ooi_fields = [
        (field, model_field.annotation == Reference, model_field.is_required())
        for field, model_field in ooi_type.model_fields.items()
        if field not in skip_properties
    ]

    kwargs: dict[str, Reference | str | None] = {}
    extra_declarations: list[NormalizerDeclaration] = []

    for field, is_reference, required in ooi_fields:
        if is_reference and required:
            try:
                referenced_ooi = get_or_create_reference(field, values.get(field), reference_cache)

                extra_declarations.append(NormalizerDeclaration(ooi=referenced_ooi))
                kwargs[field] = referenced_ooi.reference
            except IndexError:
                if required:
                    raise IndexError(
                        f"Required referenced primary-key field '{field}' not set "
                        f"and no default present for Type '{ooi_type_name}'."
                    )
                else:
                    kwargs[field] = None
        else:
            kwargs[field] = values.get(field)

    return ooi_type(**kwargs), extra_declarations


def get_or_create_reference(ooi_type_name: str, value: str | None, reference_cache: dict) -> OOI:
    ooi_type_name = next(filter(lambda x: x.casefold() == ooi_type_name.casefold(), OOI_TYPES.keys()))

    # get from cache
    cache = reference_cache.setdefault(ooi_type_name, {})
    if value in cache:
        return cache[value]

    ooi_type = OOI_TYPES[ooi_type_name]["type"]

    # set default value if any
    if value is None:
        value = OOI_TYPES[ooi_type_name].get("default")

    # create the ooi
    kwargs = {OOI_TYPES[ooi_type_name]["argument"]: value}
    ooi = ooi_type(**kwargs)
    cache[value] = ooi

    return ooi
