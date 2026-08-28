# TODO: Use database row locking instead of threading locks, see: #4129
from __future__ import annotations

import abc
import functools
import threading
from typing import Any

import pydantic
import structlog

from scheduler import models, storage

from .errors import InvalidItemError, NotAllowedError, QueueFullError


def with_lock(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)

    return wrapper


class PriorityQueue(abc.ABC):
    """Base PriorityQueue class

    Attributes:
        logger:
            The logger for the class.
        pq_id:
            A string representing the identifier of the priority queue.
        maxsize:
            A integer representing the maximum size of the queue.
        item_type:
            A pydantic.BaseModel that describes the type of the items on the
            queue.
        allow_replace:
            A boolean that defines if the queue allows replacing an item. When
            set to True, it will update the item on the queue.
        allow_updates:
            A boolean that defines if the queue allows updates of items on the
            queue. When set to True, it will update the item on the queue.
        allow_priority_updates:
            A boolean that defines if the queue allows priority updates of
            items on the queue. When set to True, it will update the item on
            the queue.
        pq_store:
            A PriorityQueueStore instance that will be used to store the items
            in a persistent way.
        lock:
            A threading.Lock instance that will be used to lock the queue
            operations.
    """

    def __init__(
        self,
        pq_id: str,
        maxsize: int,
        item_type: Any,
        pq_store: storage.stores.PriorityQueueStore,
        allow_replace: bool = False,
        allow_updates: bool = False,
        allow_priority_updates: bool = False,
    ):
        """Initialize the priority queue.

        Args:
            pq_id:
                The id of the queue.
            maxsize:
                The maximum size of the queue.
            item_type:
                The type of the items in the queue.
            allow_replace:
                A boolean that defines if the queue allows replacing an item.
                When set to True, it will update the item on the queue.
            allow_updates:
                A boolean that defines if the queue allows updates of items on
                the queue. When set to True, it will update the item on the
                queue.
            allow_priority_updates:
                A boolean that defines if the queue allows priority updates of
                items on the queue. When set to True, it will update the item
                on the queue.
            pq_store:
                A PriorityQueueStore instance that will be used to store the
                items in a persistent way.
        """
        self.logger: structlog.BoundLogger = structlog.getLogger(__name__)
        self.pq_id: str = pq_id
        self.maxsize: int = maxsize
        self.item_type: Any = item_type
        self.allow_replace: bool = allow_replace
        self.allow_updates: bool = allow_updates
        self.allow_priority_updates: bool = allow_priority_updates
        self.pq_store: storage.stores.PriorityQueueStore = pq_store
        self.lock: threading.RLock = threading.RLock()

    @with_lock
    def pop(self, limit: int | None = None, filters: storage.filters.FilterRequest | None = None) -> list[models.Task]:
        """Remove and return the highest priority items from the queue.
        Optionally apply filters to the queue.

        Args:
            filters: A FilterRequest instance that defines the filters

        Returns:
            The highest priority items from the queue.
        """
        items = self.pq_store.pop(self.pq_id, limit, filters)
        if not items:
            return []

        self.pq_store.bulk_update_status(self.pq_id, [item.id for item in items], models.TaskStatus.DISPATCHED)

        return items

    @with_lock
    def push(self, task: models.Task) -> models.Task:
        """Push an item onto the queue.

        Args:
            task: The item to be pushed onto the queue.

        Returns:
            The item that was pushed onto the queue.

        Raises:
            NotAllowedError: If the item is not allowed to be pushed.

            InvalidItemError: If the item is not valid.

            QueueFullError: If the queue is full.

            ItemNotFoundError: If the item is not found on the queue.
        """
        if not isinstance(task, models.Task):
            raise InvalidItemError("The item is not of type Task")

        if not self._is_valid_item(task.data):
            raise InvalidItemError(f"Task must be of type {self.item_type}")

        if not task.priority:
            raise InvalidItemError("Task must have a priority")

        if self.full() and task.priority > 1:
            raise QueueFullError(f"Queue {self.pq_id} is full.")

        # We try to get the item from the queue by a specified identifier of
        # that item by the implementation of the queue. We don't do this by
        # the item itself or its hash because this might have been changed
        # and we might need to update that.
        item_on_queue = self.get_item_by_identifier(task)

        # Item on queue and data changed
        item_changed = item_on_queue and task.data != item_on_queue.data

        # Item on queue and priority changed
        priority_changed = item_on_queue and task.priority != item_on_queue.priority

        allowed = any(
            (
                item_on_queue and self.allow_replace,
                item_on_queue and self.allow_updates and item_changed,
                item_on_queue and self.allow_priority_updates and priority_changed,
                not item_on_queue,
            )
        )

        if not allowed:
            message = f"Item already on queue {self.pq_id}. "

            if item_on_queue and not self.allow_replace:
                message += "Item already on queue, we're not allowed to replace the item that is already on the queue."
            elif item_on_queue and item_changed and not self.allow_updates:
                message += (
                    "Item already on queue, and item changed, we're not "
                    "allowed to update the item that is already on the queue."
                )
            elif item_on_queue and priority_changed and not self.allow_priority_updates:
                message += (
                    "Item already on queue, and priority changed, "
                    "we're not allowed to update the priority of the item "
                    "that is already on the queue."
                )

            raise NotAllowedError(message)

        # If already on queue update the item, else create a new one
        if not item_on_queue:
            task.hash = self.create_hash(task)
            task.status = models.TaskStatus.QUEUED
            item_db = self.pq_store.push(task)
            return item_db

        # Update the item with the new data
        patch_data = task.dict(exclude_unset=True)
        updated_task = item_on_queue.model_copy(update=patch_data)

        # Update the item in the queue
        self.pq_store.update(self.pq_id, updated_task)
        return updated_task

    @with_lock
    def peek(self, index: int) -> models.Task | None:
        """Return the item at index without removing it.

        Args:
            index: The index of the item to be returned.

        Returns:
            The item at index.
        """
        return self.pq_store.peek(self.pq_id, index)

    @with_lock
    def remove(self, task: models.Task) -> None:
        """Remove an item from the queue.

        Args:
            task: The item to be removed from the queue.

        Returns:
            The item that was removed from the queue.
        """
        self.pq_store.remove(self.pq_id, task.id)

    @with_lock
    def clear(self) -> None:
        """Clear the queue."""
        self.pq_store.clear(self.pq_id)

    @with_lock
    def empty(self) -> bool:
        """Return True if the queue is empty, False otherwise."""
        return self.pq_store.empty(self.pq_id)

    @with_lock
    def qsize(self) -> int:
        """Return the size of the queue."""
        return self.pq_store.qsize(self.pq_id)

    @with_lock
    def full(self) -> bool:
        """Return True if the queue is full, False otherwise."""
        if self.maxsize is None or self.maxsize == 0:
            return False

        return self.qsize() >= self.maxsize

    @with_lock
    def is_item_on_queue(self, task: models.Task) -> bool:
        """Check if an item is on the queue.

        Args:
            task: The item to be checked.

        Returns:
            True if the item is on the queue, False otherwise.
        """
        identifier = self.create_hash(task)
        item = self.pq_store.get_item_by_hash(self.pq_id, identifier)
        if item is None:
            return False

        return True

    @with_lock
    def is_item_on_queue_by_hash(self, item_hash: str) -> bool:
        """Check if an item is on the queue by its hash.

        Args:
            item_hash: The hash of the item to be checked.

        Returns:
            True if the item is on the queue, False otherwise.
        """
        item = self.pq_store.get_item_by_hash(self.pq_id, item_hash)
        return item is not None

    @with_lock
    def get_item_by_identifier(self, task: models.Task) -> models.Task | None:
        """Get an item from the queue by its identifier.

        Args:
            task: The item to be checked.

        Returns:
            The item if found, None otherwise.
        """
        identifier = self.create_hash(task)
        item = self.pq_store.get_item_by_hash(self.pq_id, identifier)
        return item

    def _is_valid_item(self, item: Any) -> bool:
        """Validate the item to be pushed into the queue.

        Args:
            item: The item to be validated.

        Returns:
            A boolean, True if the item is valid, False otherwise.
        """
        try:
            self.item_type.model_validate(item)
        except pydantic.ValidationError:
            return False

        return True

    def dict(self, include_pq: bool = True) -> dict[str, Any]:
        """Return a dictionary representation of the queue."""
        response = {
            "id": self.pq_id,
            "size": self.qsize(),
            "maxsize": self.maxsize,
            "item_type": self.item_type.__name__,
            "allow_replace": self.allow_replace,
            "allow_updates": self.allow_updates,
            "allow_priority_updates": self.allow_priority_updates,
        }

        if include_pq:
            response["pq"] = self.pq_store.get_items_by_scheduler_id(self.pq_id)

        return response

    def create_hash(self, task: models.Task) -> str:
        """Create a hash for the given item. This hash is used to determine if
        the item is already in the queue.

        Abstract method to be implemented by the concrete implementation of
        the queue. It needs to create a unique identifier for the item on
        the queue.

        Args:
            task: The item to be hashed.

        Returns:
            A string representing the hash of the item.
        """
        item = self.item_type(**task.data)
        return item.hash
