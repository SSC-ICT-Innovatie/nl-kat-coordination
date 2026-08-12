from typing import Any

import fastapi
from fastapi import status

from scheduler import context


class RootAPI:
    """Root API handler."""

    def __init__(self, api: fastapi.FastAPI, ctx: context.AppContext):
        self.api = api
        self.ctx = ctx

        self.api.add_api_route(
            path="/", endpoint=self.root, methods=["GET"], status_code=status.HTTP_200_OK, description="Root endpoint"
        )

    def root(self) -> Any:
        return None
