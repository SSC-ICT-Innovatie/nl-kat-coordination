from queue import Full


class QueueEmptyError(Exception):
    pass


class NotAllowedError(Exception):
    pass


class InvalidItemError(ValueError):
    pass


class QueueFullError(Full):
    pass


class ItemNotFoundError(Exception):
    pass
