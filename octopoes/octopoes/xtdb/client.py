import functools
from collections.abc import Callable
from datetime import datetime, timezone
from enum import Enum
from json import JSONDecodeError
from typing import Any

import httpx
import structlog
from httpx import HTTPError, HTTPStatusError, Response, codes
from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter

from octopoes.config.settings import Settings
from octopoes.models.transaction import TransactionRecord
from octopoes.xtdb.exceptions import NodeNotFound, XTDBException
from octopoes.xtdb.query import Query

logger = structlog.get_logger(__name__)
settings = Settings()


class OperationType(Enum):
    PUT = "put"
    DELETE = "delete"
    MATCH = "match"
    EVICT = "evict"
    FN = "fn"


Operation = tuple[OperationType, str | dict[str, Any], datetime | None]


class Transaction(BaseModel):
    operations: list[Operation] = Field(alias="tx-ops")
    model_config = ConfigDict(populate_by_name=True)


class XTDBStatus(BaseModel):
    version: str | None = None
    revision: str | None = None
    indexVersion: int | None = None
    consumerState: str | None = None
    kvStore: str | None = None
    estimateNumKeys: int | None = None
    size: int | None = None


@functools.cache
def _get_xtdb_http_session(base_url: str) -> httpx.Client:
    return httpx.Client(
        base_url=base_url,
        headers={"Accept": "application/json"},
        transport=httpx.HTTPTransport(retries=3),
        timeout=settings.outgoing_request_timeout,
    )


class XTDBHTTPClient:
    def __init__(self, base_url: str, node: str | None):
        self.node = node
        self._session = _get_xtdb_http_session(base_url)

    @staticmethod
    def _verify_response(response: Response) -> None:
        try:
            response.raise_for_status()
        except HTTPStatusError as e:
            try:
                if response.json()["error"] == "Node not found":
                    raise NodeNotFound() from e
            except (KeyError, JSONDecodeError):
                pass
            raise e

    @property
    def node_url(self) -> str:
        if not self.node:
            raise ValueError("Node not selected, cannot construct URL.")
        return f"/{self.node}"

    def status(self) -> XTDBStatus:
        res = self._session.get(f"{self.node_url}/status")

        self._verify_response(res)
        return XTDBStatus.model_validate_json(res.content)

    def get_entity(self, entity_id: str, valid_time: datetime | None = None) -> dict:
        if valid_time is None:
            valid_time = datetime.now(timezone.utc)
        res = self._session.get(
            f"{self.node_url}/entity", params={"eid": entity_id, "valid-time": valid_time.isoformat()}
        )

        self._verify_response(res)
        return res.json()

    def get_entity_history(
        self,
        entity_id: str,
        *,
        sort_order: str = "asc",  # Or: "desc"
        with_docs: bool = False,
        has_doc: bool | None = None,
        offset: int = 0,
        limit: int | None = None,
        indices: list[int] | None = None,
    ) -> list[TransactionRecord]:
        params = {
            "eid": entity_id,
            "sort-order": sort_order,
            "history": "true",
            "with-docs": "true" if with_docs else "false",
        }

        res = self._session.get(f"{self.node_url}/entity", params=params)
        self._verify_response(res)
        transactions: list[TransactionRecord] = TypeAdapter(list[TransactionRecord]).validate_json(res.content)

        if has_doc is True:  # The doc is None if and only if the hash is  "0000000000000000000000000000000000000000"
            transactions = [transaction for transaction in transactions if transaction.content_hash != 40 * "0"]

        if has_doc is False:  # The doc is None if and only if the hash is  "0000000000000000000000000000000000000000"
            transactions = [transaction for transaction in transactions if transaction.content_hash == 40 * "0"]

        if indices:
            return [tx for i, tx in enumerate(transactions) if i in indices or i - len(transactions) in indices]

        if limit:
            return transactions[offset : offset + limit]

        if offset:
            return transactions[offset:]

        return transactions

    def query(self, query: str | Query, valid_time: datetime | None = None) -> list[list[Any]]:
        if valid_time is None:
            valid_time = datetime.now(timezone.utc)
        res = self._session.post(
            f"{self.node_url}/query",
            params={"valid-time": valid_time.isoformat()},
            content=" ".join(str(query).split()),
            headers={"Content-Type": "application/edn"},
        )
        self._verify_response(res)
        return res.json()

    def await_transaction(self, transaction_id: int) -> None:
        self._session.get(f"{self.node_url}/await-tx", params={"txId": transaction_id})
        logger.info("Transaction completed [txId=%s]", transaction_id)

    def submit_transaction(self, operations: list[Operation]) -> None:
        res = self._session.post(
            f"{self.node_url}/submit-tx", json=Transaction(operations=operations).model_dump(by_alias=True, mode="json")
        )

        self._verify_response(res)
        self.await_transaction(res.json()["txId"])

    def list_nodes(self) -> list[str]:
        res = self._session.get("/list-nodes")
        self._verify_response(res)
        return res.json()["nodes"]

    def create_node(self) -> None:
        try:
            res = self._session.post("/create-node", json={"node": self.node})
            self._verify_response(res)
        except HTTPError as e:
            logger.exception("Failed creating node %s", self._session.base_url)
            raise XTDBException("Could not create node") from e

    def delete_node(self) -> None:
        try:
            res = self._session.post("/delete-node", json={"node": self.node})
            self._verify_response(res)
        except HTTPError as e:
            if isinstance(e, HTTPStatusError) and e.response.status_code == codes.NOT_FOUND:
                raise NodeNotFound from e

            logger.exception("Failed deleting node")

            raise XTDBException("Could not delete node") from e

    def export_transactions(self):
        res = self._session.get(f"{self.node_url}/tx-log?with-ops?=true", headers={"Accept": "application/json"})
        self._verify_response(res)
        return res.json()

    def sync(self, timeout: int | None = None) -> Any:
        params = {}

        if timeout is not None:
            params["timeout"] = timeout

        res = self._session.get(f"{self.node_url}/sync", params=params)
        self._verify_response(res)

        return res.json()

    def latest_completed_tx(self) -> JsonValue:
        res = self._session.get(f"{self.node_url}/latest-completed-tx")
        self._verify_response(res)
        return res.json()


class XTDBSession:
    def __init__(self, client: XTDBHTTPClient):
        self.client = client

        self._operations: list[Operation] = []
        self.post_commit_callbacks: list[Callable[[], None]] = []

    def __enter__(self):
        return self

    def __exit__(self, _exc_type: type[Exception], _exc_value: str, _exc_traceback: str) -> None:
        self.commit()

    def add(self, operation: Operation) -> None:
        self._operations.append(operation)

    def put(self, document: str | dict[str, Any], valid_time: datetime) -> None:
        self.add((OperationType.PUT, document, valid_time))

    def commit(self, sync: bool = False) -> int:
        """commits all pending operations to the database,
        and optionally call sync to wait for processing to finish
        and returns the amount of processed operations."""
        if not self._operations:
            self.reset()
            return 0

        count = len(self._operations)
        logger.debug("Committing XTDBSession with %i transactions", count, operations=self._operations)
        self.client.submit_transaction(self._operations)

        if self.post_commit_callbacks:
            for callback in self.post_commit_callbacks:
                callback()
            logger.info(
                "Called %i callbacks after committing XTDBSession with %i transactions",
                len(self.post_commit_callbacks),
                count,
            )
        self.reset()

        if sync:
            self.client.sync()
        return count

    def reset(self) -> None:
        """Resets the session, and removes all operations and callbacks."""
        self._operations = []
        self.post_commit_callbacks = []

    def sync(self) -> None:
        logger.info("Called Sync on XTDB client, waiting for database to complete transactions.")
        self.client.sync()

    def listen_post_commit(self, callback: Callable[[], None]) -> None:
        """Registers a callback on the session, which will be called after the
        session is committed."""
        self.post_commit_callbacks.append(callback)
