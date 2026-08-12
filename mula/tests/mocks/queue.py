from scheduler import models
from scheduler.schedulers.queue import PriorityQueue
from scheduler.utils import dict_utils


class MockPriorityQueue(PriorityQueue):
    def create_hash(self, p_item: models.Task) -> str:
        return dict_utils.deep_get(p_item.model_dump(), ["data", "id"])
