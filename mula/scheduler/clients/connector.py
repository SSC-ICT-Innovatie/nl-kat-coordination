import socket
import time
from collections.abc import Callable
from typing import Any

import httpx
import structlog


class Connector:
    """A class that provides methods to check if a host is available and healthy."""

    def __init__(self):
        self.logger = structlog.getLogger(self.__class__.__name__)

    def is_host_available(self, hostname: str, port: int) -> bool:
        """Check if the host is available.

        Args:
            hostname: A string representing the hostname.
            port: An integer representing the port number.

        Returns:
            A boolean
        """
        try:
            socket.create_connection((hostname, port))
            return True
        except OSError:
            return False

    def is_host_healthy(self, host: str, health_endpoint: str) -> bool:
        """Check if host is healthy by inspecting the host's health endpoint.

        Args:
            host: A string representing the hostname.
            health_endpoint: A string representing the health endpoint.

        Returns:
            A boolean
        """
        try:
            url = f"{host}/{health_endpoint}"
            response = httpx.get(url, timeout=5)
            healthy = response.json().get("healthy")
            return healthy
        except httpx.HTTPError as exc:
            self.logger.warning("Exception: %s", exc)
            return False

    def retry(self, func: Callable, *args: Any, **kwargs: Any) -> bool:
        """Retry a function until it returns True.

        Args:
            func: A python callable that needs to be retried.

        Returns:
            A boolean signifying whether or not the func was executed successfully.
        """
        for i in range(10):
            if func(*args, **kwargs):
                self.logger.info(
                    "Function %s, executed successfully. Retry count: %d",
                    func.__name__,
                    i,
                    name=func.__name__,
                    args=args,
                    kwargs=kwargs,
                )
                return True

            self.logger.warning(
                "Function %s, failed. Retry count: %d", func.__name__, i, name=func.__name__, args=args, kwargs=kwargs
            )

            time.sleep(10)

        return False
