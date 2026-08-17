from __future__ import annotations


class ObjectNotFoundException(Exception):
    def __init__(self, value: str):
        self.value = value


class TypeNotFound(ValueError):
    pass


class BitNoOperation(ValueError):
    """Used to signal that the BIT that ran on this Input OOI will never Do any
    work, and as such no future Operations should ever be considered."""

    pass
