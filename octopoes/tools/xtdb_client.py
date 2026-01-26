import datetime
from functools import cached_property

import httpx
from pydantic import JsonValue

PutTransaction = (
    tuple[str, dict]
    | tuple[str, dict, str | datetime.datetime]
    | tuple[str, dict, str | datetime.datetime, str | datetime.datetime]
)

FnTransaction = (tuple[str, str, str, ...])

DeleteTransaction = (
    tuple[str] | tuple[str, str | datetime.datetime] | tuple[str, str | datetime.datetime, str | datetime.datetime]
)

EvictTransaction = DeleteTransaction

SimpleTransactions = list[PutTransaction | DeleteTransaction | EvictTransaction]

MatchTransaction = (
    tuple[str, str, dict, SimpleTransactions] | tuple[str, str, dict, str | datetime.datetime, SimpleTransactions]
)

TransactionType = PutTransaction | DeleteTransaction | EvictTransaction | MatchTransaction | FnTransaction


class XTDBClient:
    def __init__(
        self, base_url: str, node: str | None = None, timeout: int | None = None, headers: dict[str,str] | None = None
    ):
        self.base_url = base_url
        self.node = node
        self.timeout = timeout
        self.headers = headers or {"Accept": "application/json"}

    @cached_property
    def server(self):
        return httpx.Client(base_url=f"{self.base_url}/_xtdb/", headers=self.headers, timeout=self.timeout)

    @cached_property
    def client(self):
        if not self.node:
            raise ValueError("No Node given, cannot perform node based query.")
        return httpx.Client(base_url=f"{self.base_url}/_xtdb/{self.node}", headers=self.headers, timeout=self.timeout)

    def nodes(self) -> JsonValue:
        res = self.server.get("/list-nodes")

        return res.json()["nodes"]

    def create_node(self) -> JsonValue:
        res = self.server.post(
            "/create-node", content=f'{{:node "{self.node}"}}', headers={"Content-Type": "application/edn"}
        )

        return res.json()

    def delete_node(self) -> JsonValue:
        res = self.server.post(
            "/delete-node", content=f'{{:node "{self.node}"}}', headers={"Content-Type": "application/edn"}
        )

        return res.json()

    def status(self) -> JsonValue:
        res = self.client.get("/status")

        return res.json()

    def query(
        self,
        query: str = "{:query {:find [ ?var ] :where [[?var :xt/id ]]}}",
        valid_time: datetime.datetime | None = None,
        tx_time: datetime.datetime | None = None,
        tx_id: int | None = None,
    ) -> JsonValue:
        params = {}
        if valid_time is not None:
            params["valid-time"] = valid_time.isoformat()
        if tx_time is not None:
            params["tx-time"] = tx_time.isoformat()
        if tx_id is not None:
            params["tx-id"] = str(tx_id)

        res = self.client.post("/query", params=params, content=query, headers={"Content-Type": "application/edn"})

        try:
            return res.json()
        except Exception:
            raise ValueError(res.content)

    def entity(
        self,
        key: str,
        valid_time: datetime.datetime | None = None,
        tx_time: datetime.datetime | None = None,
        tx_id: int | None = None,
    ) -> JsonValue:
        params = {"eid": key}
        if valid_time is not None:
            params["valid-time"] = valid_time.isoformat()
        if tx_time is not None:
            params["tx-time"] = tx_time.isoformat()
        if tx_id is not None:
            params["tx-id"] = str(tx_id)

        res = self.client.get("/entity", params=params)

        return res.json()

    def history(self, key: str, with_corrections: bool, with_docs: bool) -> JsonValue:
        params = {"eid": key, "history": True, "sortOrder": "asc"}
        if with_corrections:
            params["with-corrections"] = "true"
        if with_docs:
            params["with-docs"] = "true"

        res = self.client.get("/entity", params=params)

        return res.json()

    def entity_tx(
        self,
        key: str,
        valid_time: datetime.datetime | None = None,
        tx_time: datetime.datetime | None = None,
        tx_id: int | None = None,
    ) -> JsonValue:
        params = {"eid": key}
        if valid_time is not None:
            params["valid-time"] = valid_time.isoformat()
        if tx_time is not None:
            params["tx-time"] = tx_time.isoformat()
        if tx_id is not None:
            params["tx-id"] = str(tx_id)
        res = self.client.get("/entity-tx", params=params)

        return res.json()

    def attribute_stats(self) -> JsonValue:
        res = self._client.get("/attribute-stats")

        return res.json()

    def sync(self, timeout: int | None) -> JsonValue:
        if timeout is not None:
            res = self.client.get("/sync", params={"timeout": timeout})
        else:
            res = self.client.get("/sync")

        return res.json()

    def await_tx(self, transaction_id: int, timeout: int | None) -> JsonValue:
        params = {"txId": transaction_id}
        if timeout is not None:
            params["timeout"] = timeout
        res = self.client.get("/await-tx", params=params)

        return res.json()

    def await_tx_time(self, transaction_time: datetime.datetime, timeout: int | None) -> JsonValue:
        params = {"tx-time": transaction_time.isoformat()}
        if timeout is not None:
            params["timeout"] = str(timeout)
        res = self.client.get("/await-tx-time", params=params)

        return res.json()

    def tx_log(self, after_tx_id: int | None, with_ops: bool) -> JsonValue:
        params = {}
        if after_tx_id is not None:
            params["after-tx-id"] = after_tx_id
        if with_ops:
            params["with-ops?"] = True

        res = self.client.get("/tx-log", params=params)

        return res.json()


    def origins(
        self, 
        entity: str,
        include_params: bool = False,
        valid_time: datetime.datetime | None = None,
        tx_time: datetime.datetime | None = None,
        tx_id: int | None = None,
    ) -> JsonValue:
        if include_params:
            query = f"""
            {{
              :query {{
                :find [(pull ?x [*])]
                :in [_type _result]
                :where [
                  [?e :type _type]
                  [?e :result _result]

                  (or-join [?x ?e]
                    ;; the Origin itself
                    [(= ?x ?e)]

                    ;; linked OriginParameter
                    [
                      [?x :type "OriginParameter"]
                      [?x :origin_id ?e]
                    ])
                ]
              }}
              :in-args ["Origin" "{entity}"]
            }}"""
        else:
            query = f"""{{
                :query {{
                    :find [(pull ?e [*])]
                    :in [_type _result]
                    :where [[?e :type _type] [?e :result _result]]
                }}
                :in-args [ "Origin" "{entity}" ]
            }}"""
        return self.query(query, valid_time, tx_time, tx_id)


    def def submit_tx(self, transactions: list[TransactionType], valid_time: datetime.datetime | None = None) -> JsonValue:
        data = {"tx-ops": transactions}
        if valid_time:
            data["valid-time"] = valid_time.isoformat()
        res = self.client.post("/submit-tx", json=data)

        return res.json()

    def tx_committed(self, txid: int) -> JsonValue:
        res = self.client.get("/tx-committed", params={"txId": txid})

        return res.json()

    def latest_completed_tx(self) -> JsonValue:
        res = self.client.get("/latest-completed-tx")

        return res.json()

    def latest_submitted_tx(self) -> JsonValue:
        res = self.client.get("/latest-submitted-tx")

        return res.json()

    def active_queries(self) -> JsonValue:
        res = self.client.get("/active-queries")

        return res.json()

    def recent_queries(self) -> JsonValue:
        res = self.client.get("/recent-queries")

        return res.json()

    def slowest_queries(self) -> JsonValue:
        res = self.client.get("/recent-queries")

        return res.json()
