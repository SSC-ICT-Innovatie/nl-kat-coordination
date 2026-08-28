import time
import urllib.parse
from collections.abc import MutableMapping
from typing import Any

import httpx
import structlog
from httpx import HTTPTransport, Limits

from ..connector import Connector  # noqa: TID252


class HTTPService(Connector):
    """HTTPService exposes methods to make http requests to services that
    typically expose rest api endpoints

    Attributes:
        logger:
            The logger for the class.
        session:
            A httpx.Client object.
        name:
            A string describing the name of the service. This is used args
            an identifier.
        source:
            As string defining the request user agent of HTTP request made from
            this HTTPService instance. This helps services differentiate from
            where the requests came from.
        host:
            A string url formatted reference to the host of the service
        headers:
            A dict containing the request headers.
        health_endpoint:
            A string defining the health endpoint for the service. Used too
            determine whether a host is healthy.
        timeout:
            An integer defining the timeout of requests.
    """

    name: str | None = None
    health_endpoint: str | None = "health"

    def __init__(self, host: str, source: str, timeout: int = 10, pool_connections: int = 10, retries: int = 5):
        """Initializer of the HTTPService class. During initialization the
        host will be checked if it is available and healthy.

        Args:
            host:
                A string url formatted reference to the host of the service
            source:
                A string defining the request source of HTTP request made from
                this HTTPService instance. This helps services differentiate
                from where the requests came from.
            timeout:
                An integer defining the timeout of requests.
            pool_connections:
                The number of connections kept alive in the pool.
            retries:
                An integer defining the number of retries to make before
                giving up.
        """
        super().__init__()

        self.logger: structlog.BoundLogger = structlog.getLogger(self.__class__.__name__)
        self.host: str = host
        self.timeout: int = timeout
        self.pool_connections: int = pool_connections
        self.retries: int = retries
        self.source: str = source
        transport = HTTPTransport(retries=self.retries, limits=Limits(max_connections=self.pool_connections))
        self.session = httpx.Client(transport=transport, timeout=self.timeout)

        if self.source:
            self.session.headers["User-Agent"] = self.source

        self._do_checks()

    def get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """Execute a HTTP GET request

        Args:
            url:
                A string url formatted reference to the host of the service
            params:
                A dict to set the query parameters for the request

        Returns:
            A request.Response object
        """
        response = self._request_with_backoff(
            method="GET", url=url, headers=self.headers, params=params, timeout=self.timeout
        )
        self.logger.debug("Made GET request to %s.", url, name=self.name, url=url)

        response.raise_for_status()

        return response

    def post(self, url: str, payload: dict[str, Any], params: dict[str, Any] | None = None) -> httpx.Response:
        """Execute a HTTP POST request

        Args:
            headers:
                A dict to set additional headers for the request.
            params:
                A dict to set the query parameters for the request

        Returns:
            A request.Response object
        """
        response = self._request_with_backoff(
            method="POST", url=url, headers=self.headers, params=params, data=payload, timeout=self.timeout
        )
        self.logger.debug("Made POST request to %s.", url, name=self.name, url=url, payload=payload)

        response.raise_for_status()

        return response

    def _request_with_backoff(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        for i in range(1, self.retries + 1):
            try:
                response = self.session.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.RequestError as exc:
                if i == self.retries:
                    raise exc

                self.logger.warning("Retrying %s request to %s (attempt %d/%d)", method, url, i, self.retries)
                delay = min(2**i, 60)  # Exponential backoff with a max delay of 60 seconds
                time.sleep(delay)

        raise RuntimeError("Request failed after maximum retries")

    @property
    def headers(self) -> MutableMapping[str, str]:
        return self.session.headers

    def _do_checks(self) -> None:
        """Do checks whether a host is available and healthy."""
        if not self.host:
            self.logger.warning("No host defined for service %s", self.name)
            return

        parsed_url = urllib.parse.urlparse(self.host)
        hostname, port = parsed_url.hostname, parsed_url.port

        if port is None and parsed_url.scheme is not None:
            port = 80 if parsed_url.scheme == "http" else 443

        if hostname is None or port is None:
            self.logger.warning("Not able to parse hostname and port from %s", self.host, host=self.host)
            return

        if self.host is not None and self.retry(self.is_host_available, hostname, port) is False:
            raise RuntimeError(f"Host {self.host} is not available.")

        if (
            self.health_endpoint is not None
            and self.retry(self.is_host_healthy, self.host, self.health_endpoint) is False
        ):
            raise RuntimeError(f"Service {self.name} is not running.")

    def is_healthy(self) -> bool:
        """Check if host is healthy by inspecting the host's health endpoint.

        Returns:
            A boolean
        """
        if self.host is None:
            self.logger.warning("Host is not set.")
            return False

        if self.health_endpoint is None:
            self.logger.warning("Health endpoint is not set.")
            return False

        return self.is_host_healthy(self.host, self.health_endpoint)
