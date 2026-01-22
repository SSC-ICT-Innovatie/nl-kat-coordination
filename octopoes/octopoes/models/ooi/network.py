from __future__ import annotations

from enum import Enum
from ipaddress import IPv4Address, IPv4Network, IPv6Address, ip_network
from typing import Annotated, Literal

import yaml
from pydantic import Field, field_serializer

from octopoes.models import OOI, Reference
from octopoes.models.persistence import ReferenceField


class Network(OOI):
    """Represents the Network object.

    Can be used to describe how/where scans took place.

    Example value
    -------------
    internet
    """

    object_type: Literal["Network"] = "Network"

    name: str

    _natural_key_attrs = ["name"]
    _traversable = False

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return reference.tokenized.name

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: Network) -> yaml.Node:
        return dumper.represent_mapping("!Network", {**cls.get_ooi_yml_repr_dict(data), "name": data.name})


class IPAddress(OOI):
    """Represents IPv4 or IPv6 address objects."""

    address: IPv4Address | IPv6Address
    network: Reference = ReferenceField(Network)

    _natural_key_attrs = ["network", "address"]
    _information_value = ["address"]

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return reference.tokenized.address

    @classmethod
    def yml_constructor(cls, loader: yaml.SafeLoader, node):
        """It should be override again in child classes"""
        values: dict = loader.construct_mapping(node)
        ip_address_: str = values.get("address", "")
        if isinstance(ip_network(ip_address_), IPv4Network):
            return IPAddressV4(**values)
        return IPAddressV6(**values)


class IPAddressV4(IPAddress):
    """Represents IPv4 address objects.

    Example value
    -------------
    192.168.1.2
    """

    object_type: Literal["IPAddressV4"] = "IPAddressV4"
    address: IPv4Address

    netblock: Reference | None = ReferenceField(
        "IPV4NetBlock", optional=True, max_issue_scan_level=0, max_inherit_scan_level=4, default=None
    )

    @field_serializer("address")
    def serialize_address(self, address: IPv4Address, _info):
        return address.exploded

    _reverse_relation_names = {"network": "ip_v4_addresses", "netblock": "ip_v4_addresses"}

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: IPAddressV4) -> yaml.Node:
        return dumper.represent_mapping(
            "!IPAddressV4",
            {
                **cls.get_ooi_yml_repr_dict(data),
                "address": data.address.exploded,
                "network": data.network,
                "netblock": data.netblock,
            },
        )

    @classmethod
    def yml_constructor(cls, loader: yaml.SafeLoader, node):
        values: dict = loader.construct_mapping(node)
        return cls(**values)


class IPAddressV6(IPAddress):
    """Represents IPv6 address objects.

    Example value
    -------------
    fdf8:f53b:82e4::53
    """

    object_type: Literal["IPAddressV6"] = "IPAddressV6"
    address: IPv6Address

    netblock: Reference | None = ReferenceField(
        "IPV6NetBlock", optional=True, max_issue_scan_level=0, max_inherit_scan_level=4, default=None
    )

    @field_serializer("address")
    def serialize_address(self, address: IPv6Address, _info):
        return address.exploded

    _reverse_relation_names = {"network": "ip_v6_addresses", "netblock": "ip_v6_addresses"}

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: IPAddressV6) -> yaml.Node:
        return dumper.represent_mapping(
            "!IPAddressV6",
            {
                **cls.get_ooi_yml_repr_dict(data),
                "address": data.address.exploded,
                "network": data.network,
                "netblock": data.netblock,
            },
        )

    @classmethod
    def yml_constructor(cls, loader: yaml.SafeLoader, node):
        values: dict = loader.construct_mapping(node)
        return cls(**values)


class Protocol(Enum):
    """Represents the protocol used for ports.

    Possible value
    --------------
    tcp, udp

    Example value
    -------------
    tcp
    """

    TCP = "tcp"
    UDP = "udp"


class PortState(Enum):
    """Represents the state of the identified ports.

    This is deprecated. OpenKAT assumes that all ports are always open.

    Possible value
    --------------
    open, closed, filtered, unfiltered, open|filtered, closed|filtered

    Example value
    -------------
    closed
    """

    OPEN = "open"
    CLOSED = "closed"
    FILTERED = "filtered"
    UNFILTERED = "unfiltered"
    OPEN_FILTERED = "open|filtered"
    CLOSED_FILTERED = "closed|filtered"


class IPPort(OOI):
    """Represents the IP-Port combination.

    Possible value
    --------------
    address, protocol, port, port state

    Example value
    -------------
    192.168.1.5:22/tcp
    """

    object_type: Literal["IPPort"] = "IPPort"

    address: Reference = ReferenceField(IPAddress, max_issue_scan_level=0, max_inherit_scan_level=4)
    protocol: Protocol
    port: Annotated[int, Field(gt=0, lt=2**16)]
    state: PortState | None = None

    _natural_key_attrs = ["address", "protocol", "port"]
    _reverse_relation_names = {"address": "ports"}
    _information_value = ["protocol", "port"]

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        tokenized = reference.tokenized
        return f"{tokenized.address.address}:{tokenized.port}/{tokenized.protocol}"

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: IPPort) -> yaml.Node:
        return dumper.represent_mapping(
            "!IPPort",
            {
                **cls.get_ooi_yml_repr_dict(data),
                "address": data.address,
                "protocol": data.protocol.value,
                "port": data.port,
                "state": data.state.value if data.state else data.state,
            },
        )


class AutonomousSystem(OOI):
    """Represents the Autonomous System number object.

    Possible value
    --------------
    number, name

    Example value
    -------------
    AS1000
    """

    object_type: Literal["AutonomousSystem"] = "AutonomousSystem"

    number: str
    name: str | None
    _natural_key_attrs = ["number"]

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: AutonomousSystem) -> yaml.Node:
        return dumper.represent_mapping(
            "!AutonomousSystem", {**cls.get_ooi_yml_repr_dict(data), "number": data.number, "name": data.name}
        )


class NetBlock(OOI):
    """Represents the Netblock object for subnets."""

    network: Reference = ReferenceField(Network)

    name: str | None = None
    description: str | None = None

    announced_by: Reference | None = ReferenceField(AutonomousSystem, default=None)
    parent: Reference | None = ReferenceField("NetBlock", default=None)

    _natural_key_attrs = ["network", "start_ip", "mask"]

    _reverse_relation_names = {"announced_by": "announced_netblocks", "parent": "child_netblocks"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"{reference.tokenized.start_ip.address}/{reference.tokenized.mask}"

    @classmethod
    def yml_constructor(cls, loader: yaml.SafeLoader, node):
        """It should be override again in child classes"""
        values: dict = loader.construct_mapping(node)
        start_ip_: str = values.get("start_ip", "")
        start_ip_ = Reference.from_str(start_ip_).tokenized.address if start_ip_ else start_ip_
        if isinstance(ip_network(start_ip_), IPv4Address):
            return IPV4NetBlock(**values)
        return IPV6NetBlock(**values)


class IPV6NetBlock(NetBlock):
    """Represents the IPv6 Netblock object.

    Possible value
    --------------
    start IPv6 address, netmask

    Example value
    -------------
    2001:0002::/48
    """

    object_type: Literal["IPV6NetBlock"] = "IPV6NetBlock"

    parent: Reference | None = ReferenceField("IPV6NetBlock", default=None)

    start_ip: Reference = ReferenceField(IPAddressV6, max_issue_scan_level=4)
    mask: Annotated[int, Field(ge=0, lt=128)]

    _reverse_relation_names = {"parent": "child_netblocks", "announced_by": "announced_ipv6_netblocks"}

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: IPV6NetBlock) -> yaml.Node:
        return dumper.represent_mapping(
            "!IPV6NetBlock",
            {
                **cls.get_ooi_yml_repr_dict(data),
                "name": data.name,
                "description": data.description,
                "network": data.network,
                "announced_by": data.announced_by,
                "parent": data.parent,
                "start_ip": data.start_ip,
                "mask": data.mask,
            },
        )

    @classmethod
    def yml_constructor(cls, loader: yaml.SafeLoader, node):
        values: dict = loader.construct_mapping(node)
        return cls(**values)


class IPV4NetBlock(NetBlock):
    """Represents the IPv4 Netblock object.

    Possible value
    --------------
    start IPv4 address, netmask

    Example value
    -------------
    192.168.5.0/24
    """

    object_type: Literal["IPV4NetBlock"] = "IPV4NetBlock"

    parent: Reference | None = ReferenceField("IPV4NetBlock", default=None)

    start_ip: Reference = ReferenceField(IPAddressV4, max_issue_scan_level=4)
    mask: Annotated[int, Field(ge=0, lt=32)]

    _reverse_relation_names = {"parent": "child_netblocks", "announced_by": "announced_ipv4_netblocks"}

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: IPV4NetBlock) -> yaml.Node:
        return dumper.represent_mapping(
            "!IPV4NetBlock",
            {
                **cls.get_ooi_yml_repr_dict(data),
                "name": data.name,
                "description": data.description,
                "network": data.network,
                "announced_by": data.announced_by,
                "parent": data.parent,
                "start_ip": data.start_ip,
                "mask": data.mask,
            },
        )

    @classmethod
    def yml_constructor(cls, loader: yaml.SafeLoader, node):
        values: dict = loader.construct_mapping(node)
        return cls(**values)


IPAddressV4.model_rebuild()
IPAddressV6.model_rebuild()
NetBlock.model_rebuild()
IPV4NetBlock.model_rebuild()
IPV6NetBlock.model_rebuild()
