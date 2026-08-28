from datetime import datetime, timezone

import httpx
from pydantic import BaseModel

from scheduler.clients.errors import exception_handler
from scheduler.clients.http import HTTPService
from scheduler.models import OOI, Organisation


class ListObjectsResponse(BaseModel):
    count: int
    items: list[OOI]


class Octopoes(HTTPService):
    """A class that provides methods to interact with the Octopoes API."""

    name = "octopoes"
    health_endpoint = None

    def __init__(self, host: str, source: str, orgs: list[Organisation], pool_connections: int, timeout: int = 10):
        self.orgs: list[Organisation] = orgs
        super().__init__(host, source, timeout, pool_connections)

    @exception_handler
    def get_objects_by_object_types(
        self, organisation_id: str, object_types: list[str], scan_level: list[int]
    ) -> list[OOI]:
        """Get all oois from octopoes"""
        if scan_level is None:
            scan_level = []

        url = f"{self.host}/{organisation_id}/objects"

        params = {
            "types": object_types,
            "scan_level": [s for s in scan_level],
            "offset": 0,
            "limit": 1,
            "valid_time": datetime.now(timezone.utc),
        }

        # Get the total count of objects
        response = self.get(url, params=params)
        list_objects = ListObjectsResponse(**response.json())
        count = list_objects.count

        # Update the limit for the paginated results
        limit = 1000
        params["limit"] = limit

        # Loop over the paginated results
        oois = []
        for offset in range(0, count, limit):
            params["offset"] = offset

            try:
                response = self.get(url, params=params)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    break
                raise

            list_objects = ListObjectsResponse(**response.json())
            oois.extend([ooi for ooi in list_objects.items])

        return oois

    @exception_handler
    def get_random_objects(self, organisation_id: str, n: int, scan_level: list[int]) -> list[OOI]:
        """Get `n` random oois from octopoes"""
        if scan_level is None:
            scan_level = []

        url = f"{self.host}/{organisation_id}/objects/random"

        params = {"amount": str(n), "scan_level": [s for s in scan_level], "valid_time": datetime.now(timezone.utc)}

        try:
            response = self.get(url, params=params)
            return [OOI(**ooi) for ooi in response.json()]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.NOT_FOUND:
                return []
            raise

    @exception_handler
    def get_object(self, organisation_id: str, reference: str) -> OOI | None:
        """Get an ooi from octopoes"""
        url = f"{self.host}/{organisation_id}/object"

        try:
            response = self.get(url, params={"reference": reference, "valid_time": datetime.now(timezone.utc)})
            return OOI(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.NOT_FOUND:
                return None
            raise

    @exception_handler
    def get_object_clients(self, reference: str, clients: set[str], valid_time: datetime) -> dict[str, OOI]:
        """Return the clients from the provided list that have the given OOI at the valid_time."""
        url = f"{self.host}/object-clients"

        try:
            response = self.get(
                url, params={"reference": reference, "clients": list(clients), "valid_time": valid_time.isoformat()}
            )

            return {client: OOI(**data) for client, data in response.json().items()}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.NOT_FOUND:
                return {}
            raise

    def is_healthy(self) -> bool:
        healthy = True
        for org in self.orgs:
            if not self.is_host_healthy(self.host, f"{org.id}/health"):
                return False

        return healthy
