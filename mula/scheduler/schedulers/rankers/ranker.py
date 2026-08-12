import abc
from typing import Any

import structlog

from scheduler import context


class Ranker(abc.ABC):
    """The Ranker class is tasked with, given an object, to give a priority
    that is used for the PriorityQueue.

    An implementation will of the Ranker will likely implement the `rank`
    method. Within the ranker we include the application context since it
    will be possible to reference multiple sources and connections in
    order to make up its priority.

    Attributes:
        logger:
            The logger for the class
        ctx:
            Application context of shared data (e.g. configuration, external
            services connections).
    """

    def __init__(self, ctx: context.AppContext) -> None:
        self.logger: structlog.BoundLogger = structlog.getLogger(__name__)
        self.ctx: context.AppContext = ctx

    @abc.abstractmethod
    def rank(self, obj: Any) -> int:
        raise NotImplementedError
