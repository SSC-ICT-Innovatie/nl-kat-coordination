import time
from functools import wraps

import sqlalchemy
import structlog

from scheduler.storage.errors import StorageError

logger = structlog.getLogger(__name__)


def retry(max_retries: int = 3, retry_delay: float = 5.0):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (StorageError, sqlalchemy.exc.OperationalError, sqlalchemy.exc.InternalError) as e:
                    if i == max_retries - 1:
                        raise e

                    logger.warning(
                        "Retrying %s.%s in %f seconds (%f): %s",
                        func.__module__,
                        func.__name__,
                        retry_delay,
                        i + 1 / max_retries,
                        e,
                    )
                    time.sleep(retry_delay)

        return wrapper

    return decorator
