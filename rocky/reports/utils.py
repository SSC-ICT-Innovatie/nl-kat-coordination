import dataclasses

import structlog
from django.core.serializers.json import DjangoJSONEncoder

from octopoes.models import OOI

logger = structlog.get_logger(__name__)


def debug_json_keys(data: dict, path: list) -> None:
    for key, value in data.items():
        if not isinstance(key, str | int):
            logger.error("Key %s is type %s, path is %s", key, type(key), path)
        if isinstance(value, dict):
            debug_json_keys(value, path + [key])


class JSONEncoder(DjangoJSONEncoder):
    def default(self, o):
        if isinstance(o, OOI):
            return str(o)
        elif dataclasses.is_dataclass(o) and not isinstance(o, type):
            # is_dataclass return True if o is a dataclass or an instance, but
            # asdict only accept instances, so we need to add the "not
            # isinstance(o, type)" to make sure o is an instance not a class.
            return dataclasses.asdict(o)
        else:
            return super().default(o)
