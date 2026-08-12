import functools

import httpx
import pydantic


class ExternalServiceError(Exception):
    pass


class ExternalServiceConnectionError(ExternalServiceError):
    pass


class ExternalServiceResponseError(ExternalServiceError):
    def __init__(self, message: str, response: httpx.Response):
        super().__init__(message)
        self.response = response


class ExternalServiceValidationError(ExternalServiceError):
    pass


def exception_handler(func):
    @functools.wraps(func)
    def inner_function(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except httpx.HTTPStatusError as exc:
            raise ExternalServiceResponseError(
                f"External service returned an error: {str(exc)}", response=exc.response
            ) from exc
        except httpx.ConnectError as exc:
            raise ExternalServiceConnectionError("External service is not available.") from exc
        except pydantic.ValidationError as exc:
            raise ExternalServiceValidationError("Validation error occurred.") from exc
        except Exception as exc:
            raise ExternalServiceError("External service returned an error.") from exc

    return inner_function
