class OctopoesAPIError(Exception):
    """A catch all exception for all errors the API can produce."""


class OctopoesAPIHTTPError(OctopoesAPIError):
    """Wrapper for HTTPErrors."""


class ConnectorException(OctopoesAPIError):
    def __init__(self, value: str):
        self.value = value

    def __str__(self) -> str:
        return self.value


class RemoteException(ConnectorException):
    pass


class DecodeException(ConnectorException):
    pass
