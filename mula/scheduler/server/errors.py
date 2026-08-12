import fastapi
from fastapi import status
from fastapi.responses import JSONResponse

from scheduler import storage


class FilterError(storage.filters.errors.FilterError):
    pass


class ValidationError(Exception):
    pass


class StorageError(storage.errors.StorageError):
    pass


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


class BadRequestError(Exception):
    pass


class TooManyRequestsError(Exception):
    pass


def filter_error_handler(request: fastapi.Request, exc: FilterError):
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": f"Invalid filter(s): {exc}"})


def storage_error_handler(request: fastapi.Request, exc: StorageError):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": f"A database error occurred: {exc}"}
    )


def validation_error_handler(request: fastapi.Request, exc: ValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST, content={"detail": f"Validation error occurred: {exc}"}
    )


def conflict_error_handler(request: fastapi.Request, exc: ConflictError):
    return JSONResponse(
        headers={"Retry-After": "60"},
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": f"Conflict error occurred: {exc}"},
    )


def bad_request_error_handler(request: fastapi.Request, exc: BadRequestError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST, content={"detail": f"Bad request error occurred: {exc}"}
    )


def not_found_error_handler(request: fastapi.Request, exc: NotFoundError):
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": f"Resource not found: {exc}"})


def too_many_requests_error_handler(request: fastapi.Request, exc: TooManyRequestsError):
    return JSONResponse(status_code=status.HTTP_429_TOO_MANY_REQUESTS, content={"detail": "Too many requests"})


def http_error_handler(request: fastapi.Request, exc: fastapi.HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
