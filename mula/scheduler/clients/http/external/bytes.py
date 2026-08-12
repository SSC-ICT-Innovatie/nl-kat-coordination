import threading
import typing
from collections.abc import Callable
from functools import wraps
from typing import Any

import httpx

from scheduler.clients.errors import ExternalServiceResponseError, exception_handler
from scheduler.clients.http import HTTPService
from scheduler.models import BoefjeMeta

ClientSessionMethod = Callable[..., Any]


def retry_with_login(function: ClientSessionMethod) -> ClientSessionMethod:
    @wraps(function)
    def wrapper(self, *args, **kwargs):
        try:
            return function(self, *args, **kwargs)
        except (httpx.HTTPStatusError, ExternalServiceResponseError) as exc:
            if exc.response.status_code != 401:
                raise

            self.login()
            return function(self, *args, **kwargs)
        except Exception as exc:
            raise exc

    return typing.cast(ClientSessionMethod, wrapper)


class Bytes(HTTPService):
    """A class that provides methods to interact with the Bytes API."""

    name = "bytes"

    def __init__(self, host: str, source: str, user: str, password: str, timeout: int, pool_connections: int):
        """Initialize the Bytes service.

        Args:
            host: A string representing the host.
            source: A string representing the source.
            user: A string representing the username.
            password: A string representing the password.
            timeout: An integer representing the timeout.
        """
        self.credentials: dict[str, str] = {"username": user, "password": password}

        self.lock: threading.Lock = threading.Lock()

        super().__init__(host, source, timeout, pool_connections)

    def login(self) -> None:
        with self.lock:
            self.headers.update({"Authorization": f"bearer {self.get_token()}"})

    @staticmethod
    def _verify_response(response: httpx.Response) -> None:
        response.raise_for_status()

    def get_token(self) -> str:
        url = f"{self.host}/token"
        response = self.post(url=url, payload=self.credentials)

        self._verify_response(response)

        return str(response.json()["access_token"])

    @retry_with_login
    @exception_handler
    def get_last_run_boefje(self, boefje_id: str, input_ooi: str, organization_id: str) -> BoefjeMeta | None:
        url = f"{self.host}/bytes/boefje_meta"
        try:
            response = self.get(
                url=url,
                params={
                    "boefje_id": boefje_id,
                    "input_ooi": input_ooi,
                    "organization": organization_id,
                    "limit": 1,
                    "descending": "true",
                },
            )
            if len(response.json()) > 0:
                return BoefjeMeta(**response.json()[0])

            return None
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == httpx.codes.NOT_FOUND:
                return None
            raise

    @retry_with_login
    @exception_handler
    def get_last_run_boefje_by_organisation_id(self, organization_id: str) -> BoefjeMeta | None:
        url = f"{self.host}/bytes/boefje_meta"
        try:
            response = self.get(url=url, params={"organization": organization_id, "limit": 1, "descending": "true"})
            return BoefjeMeta(**response.json()[0])
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == httpx.codes.NOT_FOUND:
                return None
            raise
