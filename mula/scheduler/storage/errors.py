import functools

import sqlalchemy


class StorageError(Exception):
    pass


class IntegrityError(Exception):
    pass


def exception_handler(func):
    @functools.wraps(func)
    def inner_function(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except sqlalchemy.exc.DataError as exc:
            raise StorageError(f"Invalid data: {exc}") from exc
        except sqlalchemy.exc.IntegrityError as exc:
            raise IntegrityError(f"Integrity error: {exc}") from exc
        except Exception as exc:
            raise StorageError(f"An error occurred: {exc}") from exc

    return inner_function
