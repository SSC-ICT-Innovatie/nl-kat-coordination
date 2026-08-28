from collections.abc import Iterable
from datetime import datetime, timedelta
from enum import Enum
from ipaddress import IPv4Address, IPv6Address
from typing import Any

import jcs
from pydantic import AnyUrl, BaseModel
from xxhash import xxh3_128_hexdigest as xxh3

from nibbles.definitions import NibbleDefinition, get_nibble_definitions
from octopoes.models import OOI, Reference, ScanLevel
from octopoes.models.origin import Origin, OriginType
from octopoes.repositories.nibble_repository import NibbleRepository
from octopoes.repositories.ooi_repository import OOIRepository
from octopoes.repositories.origin_repository import OriginRepository
from octopoes.repositories.scan_profile_repository import ScanProfileRepository


def merge_results(
    d1: dict[OOI, dict[str, dict[tuple[Any, ...], tuple[set[OOI], bool]]]],
    d2: dict[OOI, dict[str, dict[tuple[Any, ...], tuple[set[OOI], bool]]]],
) -> dict[OOI, dict[str, dict[tuple[Any, ...], tuple[set[OOI], bool]]]]:
    """
    Merge new runner results with old runner results
    d1: runner_results
    d2: runner_results
    --> runner_results
    """
    return {
        key: {
            nibble_id: {
                arg: (
                    set(d1.get(key, {}).get(nibble_id, {}).get(arg, (set(), False))[0])
                    | set(d2.get(key, {}).get(nibble_id, {}).get(arg, (set(), False))[0]),
                    d1.get(key, {}).get(nibble_id, {}).get(arg, (set(), False))[1]
                    or d2.get(key, {}).get(nibble_id, {}).get(arg, (set(), False))[1],
                )
                for arg in set(d1.get(key, {}).get(nibble_id, {}).keys())
                | set(d2.get(key, {}).get(nibble_id, {}).keys())
            }
            for nibble_id in set(d1.get(key, {}).keys()) | set(d2.get(key, {}).keys())
        }
        for key in set(d1.keys()) | set(d2.keys())
    }


def flatten(items: Iterable[Any | Iterable[Any | None] | None]) -> Iterable[OOI]:
    """
    Retrieve OOIs as returned from the nibble
    """
    for item in items:
        if isinstance(item, OOI):
            yield item
        elif item is None:
            continue
        elif isinstance(item, Iterable):
            yield from flatten(item)
        else:
            continue


def serialize(obj: Any) -> str:
    """
    Serialize arbitrary objects
    """

    def breakdown(obj: Any) -> Iterable[str]:
        """
        Breakdown Iterable objects so they can be `model_dump`'ed
        """
        if isinstance(obj, Iterable) and not isinstance(obj, str | bytes):
            if isinstance(obj, dict):
                yield jcs.canonicalize(obj).decode()
            else:
                for item in obj:
                    yield from breakdown(item)
        else:
            if isinstance(obj, BaseModel):
                yield serialize(obj.model_dump())
            elif isinstance(obj, Enum):
                yield jcs.canonicalize(obj.value).decode()
            elif isinstance(obj, AnyUrl | IPv6Address | IPv4Address | Reference):
                yield jcs.canonicalize(str(obj)).decode()
            elif isinstance(obj, timedelta):
                yield jcs.canonicalize(obj.total_seconds()).decode()
            else:
                yield jcs.canonicalize(obj).decode()

    return "|".join(breakdown(obj))


def nibble_hasher(data: Iterable, additional: str | None = None) -> str:
    """
    Hash the nibble generated data with its content together with the nibble checksum
    """
    return xxh3("|".join([serialize(ooi) for ooi in data]) + (additional or ""))


class NibblesRunner:
    def __init__(
        self,
        ooi_repository: OOIRepository,
        origin_repository: OriginRepository,
        scan_profile_repository: ScanProfileRepository,
        nibble_repository: NibbleRepository,
    ):
        self.ooi_repository = ooi_repository
        self.origin_repository = origin_repository
        self.scan_profile_repository = scan_profile_repository
        self.nibble_repository = nibble_repository
        self.cache: dict[OOI, dict[str, dict[tuple[Any, ...], tuple[set[OOI], bool]]]] = {}
        self.nibbles: dict[str, NibbleDefinition] = get_nibble_definitions()
        self.federated: bool = True

    def update_nibbles(self, valid_time: datetime, new_nibbles: dict[str, NibbleDefinition] = get_nibble_definitions()):
        old_checksums = {nibble.id: nibble._checksum for nibble in self.nibbles.values()}
        self.nibbles = new_nibbles
        new_checksums = {nibble.id: nibble._checksum for nibble in self.nibbles.values()}
        if self.federated:
            self.register(valid_time)
        updated_nibble_ids = [
            nibble_id
            for nibble_id in new_checksums
            if nibble_id not in old_checksums or old_checksums[nibble_id] != new_checksums[nibble_id]
        ]
        self.infer(list(flatten(self.retrieve(updated_nibble_ids, valid_time).values())), valid_time)

    def list_nibbles(self) -> list[str]:
        return list(self.nibbles.keys())

    def list_available_nibbles(self) -> list[str]:
        return list(get_nibble_definitions())

    def disable(self):
        self.nibbles = {}

    def register(self, valid_time: datetime = datetime.now()):
        self.federated = True
        self.nibble_repository.put_many([nibble._ini for nibble in self.nibbles.values()], valid_time)

    def sync(self, valid_time: datetime):
        if self.federated:
            xtdb_nibble_inis = {ni["id"]: ni for ni in self.nibble_repository.get_all(valid_time)}
            for nibble in self.nibbles.values():
                xtdb_nibble_ini = xtdb_nibble_inis[nibble.id]
                if xtdb_nibble_ini["enabled"] != nibble.enabled:
                    self.nibbles[nibble.id].enabled = xtdb_nibble_ini["enabled"]

    def toggle_nibbles(self, nibble_ids: list[str], is_enabled: bool | list[bool], valid_time: datetime):
        is_enabled = is_enabled if isinstance(is_enabled, list) else [is_enabled] * len(nibble_ids)
        for nibble_id, state in zip(nibble_ids, is_enabled):
            self.nibbles[nibble_id].enabled = state
        if self.federated:
            self.nibble_repository.put_many([self.nibbles[nibble_id]._ini for nibble_id in nibble_ids], valid_time)

    def _retrieve(self, nibble_id: str, valid_time: datetime) -> list[list[Any]]:
        nibble = self.nibbles[nibble_id]
        if len(nibble.signature) > 1:
            return [list(args) for args in self.ooi_repository.nibble_query(None, nibble, valid_time)]
        else:
            t = nibble.signature[0].object_type
            if issubclass(t, OOI):
                return [[ooi] for ooi in self.ooi_repository.list_oois_by_object_types({t}, valid_time)]
            else:
                return [[]]

    def retrieve(self, nibble_ids: list[str] | None, valid_time: datetime) -> dict[str, list[list[Any]]]:
        return {
            nibble_id: self._retrieve(nibble_id, valid_time)
            for nibble_id in (nibble_ids if nibble_ids is not None else self.nibbles)
        }

    def yields(
        self, nibble_ids: list[str] | None, valid_time: datetime
    ) -> dict[str, dict[tuple[Reference | None, ...], list[Reference]]]:
        return {
            nibble_id: {
                tuple(nibblet.parameters_references): nibblet.result
                for nibblet in self.origin_repository.list_origins(
                    valid_time, origin_type=OriginType.NIBBLET, method=nibble_id
                )
                if nibblet.parameters_references is not None
            }
            for nibble_id in (nibble_ids if nibble_ids is not None else self.nibbles)
        }

    def _check_arg_scan_level(self, nibble: NibbleDefinition, arg: Iterable, valid_time: datetime) -> bool:
        scan_profiles = self.scan_profile_repository.get_bulk(
            {a.reference for a in arg if isinstance(a, OOI)}, valid_time
        )
        return nibble.check_scan_levels(
            [
                next((sp.level for sp in scan_profiles if sp.reference == a.reference), ScanLevel.L0)
                if isinstance(a, OOI)
                else ScanLevel.L0
                for a in arg
            ]
        )

    def _run(self, ooi: OOI, valid_time: datetime) -> dict[str, dict[tuple[Any, ...], tuple[set[OOI], bool]]]:
        return_value: dict[str, dict[tuple[Any, ...], tuple[set[OOI], bool]]] = {}
        nibblets = self.origin_repository.list_nibblets_by_parameter(ooi.reference, valid_time)
        for nibblet in nibblets:
            if nibblet.method in self.nibbles and ooi.reference not in nibblet.result:
                nibble = self.nibbles[nibblet.method]
                args = self.ooi_repository.nibble_query(
                    ooi,
                    nibble,
                    valid_time,
                    nibblet.parameters_references
                    if nibble.query is not None and (callable(nibble.query) or isinstance(nibble.query, str))
                    else None,
                )
                results = {
                    tuple(arg): (set(flatten([nibble(arg)])), self._check_arg_scan_level(nibble, arg, valid_time))
                    for arg in args
                    if nibblet.parameters_hash != nibble_hasher(arg, nibble._checksum)
                }
                return_value |= {nibble.id: results}
        nibblet_nibbles = {self.nibbles[nibblet.method] for nibblet in nibblets if nibblet.method in self.nibbles}

        for nibble in filter(
            lambda x: x.enabled and x not in nibblet_nibbles and any(isinstance(ooi, t) for t in x.triggers),
            self.nibbles.values(),
        ):
            if len(nibble.signature) > 1 or nibble.query is not None:
                self._write(valid_time)
            results = {
                tuple(arg): (set(flatten([nibble(arg)])), self._check_arg_scan_level(nibble, arg, valid_time))
                for arg in self.ooi_repository.nibble_query(ooi, nibble, valid_time)
            }
            return_value |= {nibble.id: results}
        self.cache = merge_results(self.cache, {ooi: return_value})
        return return_value

    def _write(self, valid_time: datetime):
        for source_ooi, results in self.cache.items():
            self.ooi_repository.save(source_ooi, valid_time)
            for nibble_id, run_result in results.items():
                for arg, (result, materialize) in run_result.items():
                    if materialize:
                        result_references = [ooi.reference for ooi in result]
                        phantom_result = []
                    else:
                        result_references = []
                        phantom_result = list(result)
                    nibble_origin = Origin(
                        method=nibble_id,
                        origin_type=OriginType.NIBBLET,
                        source=next((a.reference for a in arg if isinstance(a, OOI)), None),
                        result=result_references,
                        phantom_result=phantom_result,
                        parameters_hash=nibble_hasher(arg, self.nibbles[nibble_id]._checksum),
                        parameters_references=[
                            a.reference if isinstance(a, OOI) and not s.optional else None
                            for a, s in zip(arg, self.nibbles[nibble_id].signature)
                        ],
                        optional_references=[
                            a.reference if isinstance(a, OOI) and s.optional else None
                            for a, s in zip(arg, self.nibbles[nibble_id].signature)
                        ],
                    )
                    for ooi in filter(lambda ooi: ooi.reference in result_references, result):
                        self.ooi_repository.save(ooi, valid_time=valid_time)
                    self.origin_repository.save(nibble_origin, valid_time=valid_time)
        self.cache = {}

    def infer(self, stack: list[OOI], valid_time: datetime) -> dict[OOI, dict[str, dict[tuple[Any, ...], set[OOI]]]]:
        self.sync(valid_time)
        inferences: dict[OOI, dict[str, dict[tuple[Any, ...], set[OOI]]]] = {}
        blockset = set(stack)
        while stack:
            ooi = stack.pop()
            results = self._run(ooi, valid_time)
            if results:
                blocks = set.union(
                    set(),
                    *[
                        ooiset
                        for result in results.values()
                        for _, (ooiset, materialize) in result.items()
                        if materialize
                    ],
                )
                stack += [o for o in blocks if o not in blockset]
                blockset |= blocks
                inferences |= {
                    ooi: {
                        nibble: {arg: ooiset for arg, (ooiset, materialize) in result.items() if materialize}
                        for nibble, result in results.items()
                    }
                }
        self._write(valid_time)
        return inferences
