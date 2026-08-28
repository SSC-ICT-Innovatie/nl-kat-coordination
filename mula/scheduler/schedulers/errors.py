import functools

from scheduler.clients.errors import ExternalServiceError
from scheduler.schedulers.queue.errors import NotAllowedError, QueueFullError


def exception_handler(func):
    @functools.wraps(func)
    def inner_function(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except ExternalServiceError as exc:
            self.logger.exception("An exception occurred", exc=exc)
            return None
        except QueueFullError as exc:
            self.logger.exception("Queue is full", exc=exc)
            return None
        except NotAllowedError as exc:
            self.logger.debug(exc)
            return None
        except Exception as exc:
            self.logger.exception(exc=exc)
            raise exc

    return inner_function
