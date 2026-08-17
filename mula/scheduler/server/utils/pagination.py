from typing import Any

from fastapi import Request
from pydantic import BaseModel


class PaginatedResponse(BaseModel):
    count: int
    next: str | None
    previous: str | None
    results: list[Any]
    is_partial_count: bool = False


def create_next_url(request: Request, offset: int, limit: int, count: int) -> str | None:
    if offset + limit <= count:
        return str(request.url.include_query_params(limit=limit, offset=offset + limit))

    return None


def create_previous_url(request: Request, offset: int, limit: int) -> str | None:
    if offset - limit >= 0:
        return str(request.url.include_query_params(limit=limit, offset=offset - limit))

    return None


def paginate(
    request: Request, items: list[Any], count: int, offset: int, limit: int, is_partial_count: bool = False
) -> PaginatedResponse:
    return PaginatedResponse(
        count=count,
        next=create_next_url(request, offset, limit, count),
        previous=create_previous_url(request, offset, limit),
        results=items,
        is_partial_count=is_partial_count,
    )
