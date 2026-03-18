import json
import logging
from collections.abc import Iterable
from ipaddress import IPv4Interface, ip_interface

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import DeclaredScanProfile
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, IPV4NetBlock, IPV6NetBlock, Network

# Expects raw to be json containing a list of ip_addresses/netblocks
# (as dictionaries) and a list of domains (as dictionaries).
# The paths through the dictionaries (to the lists and through the lists)
# are defined below.
# T O D O add these variables as normalizer settings in UI.
IP_ADDRESS_LIST_PATH = ["ip_addresses"]
IP_ADDRESS_ITEM_PATH = ["address"]
DOMAIN_LIST_PATH = ["domains"]
DOMAIN_ITEM_PATH = ["name"]
INDEMNIFICATION_ITEM_PATH = ["indemnification_level"]
DEFAULT_INDEMNIFICATION_LEVEL = 3


def follow_path_in_dict(path, path_dict):
    """Follows a list of keys in a dictionary recursively."""
    if path:
        key = path[0]
        if key not in path_dict:
            raise KeyError(f"Key {key} not in {list(path_dict.keys())}")
        return follow_path_in_dict(path=path[1:], path_dict=path_dict[key])
    return path_dict


def get_indemnification_level(path_dict):
    """Return indemnification level from metadata or default."""
    try:
        indemnification_level = int(follow_path_in_dict(path=INDEMNIFICATION_ITEM_PATH, path_dict=path_dict))
        if 0 <= indemnification_level < 5:
            return indemnification_level
        raise ValueError(f"Invalid indemnificationlevel {indemnification_level}, aborting.")
    except KeyError:
        logging.info("No integer indemnification level found, using default.")
        return DEFAULT_INDEMNIFICATION_LEVEL


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    """Yields hostnames, IPv4/6 addresses or netblocks."""
    results = json.loads(raw)
    network = Network(name=input_ooi["name"])
    addresses_count, blocks_count, hostnames_count = 0, 0, 0

    for address_item in follow_path_in_dict(path=IP_ADDRESS_LIST_PATH, path_dict=results):
        interface = ip_interface(follow_path_in_dict(path=IP_ADDRESS_ITEM_PATH, path_dict=address_item))
        indemnification_level = get_indemnification_level(path_dict=address_item)
        address, mask_str = interface.with_prefixlen.split("/")
        mask = int(mask_str)

        # Decide whether we yield IPv4 or IPv6.
        if isinstance(interface, IPv4Interface):
            address_type = IPAddressV4
            block_type = IPV4NetBlock
        else:
            address_type = IPAddressV6
            block_type = IPV6NetBlock

        ip_address = address_type(address=address, network=network.reference)
        yield ip_address
        yield DeclaredScanProfile(reference=ip_address.reference, level=indemnification_level)
        addresses_count += 1

        if mask < interface.ip.max_prefixlen:
            block = block_type(start_ip=ip_address.reference, mask=mask, network=network.reference)
            yield block
            yield DeclaredScanProfile(reference=block.reference, level=indemnification_level)
            blocks_count += 1

    for hostname_data in follow_path_in_dict(path=DOMAIN_LIST_PATH, path_dict=results):
        hostname = Hostname(
            name=follow_path_in_dict(path=DOMAIN_ITEM_PATH, path_dict=hostname_data), network=network.reference
        )
        yield hostname
        yield DeclaredScanProfile(
            reference=hostname.reference, level=get_indemnification_level(path_dict=hostname_data)
        )
        hostnames_count += 1

    logging.info(
        "Yielded %d IP addresses, %d netblocks and %d hostnames on %s.",
        addresses_count,
        blocks_count,
        hostnames_count,
        network,
    )
