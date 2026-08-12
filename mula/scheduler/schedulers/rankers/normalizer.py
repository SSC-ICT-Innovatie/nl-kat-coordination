from typing import Any

from .ranker import Ranker


class NormalizerRanker(Ranker):
    """The NormalizerRanker is a ranker that is used to rank tasks based on the
    procedure listed in the `rank()` method.
    """

    def rank(self, obj: Any) -> int:
        """Ranking of normalizer tasks, we want raw files that have been
        created a long time ago to be processed earlier."""
        return int(obj.raw_data.boefje_meta.ended_at.timestamp())
