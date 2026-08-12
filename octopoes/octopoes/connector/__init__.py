class ConnectorException(Exception):
    def __init__(self, value: str):
        self.value = value

    def __str__(self) -> str:
        return self.value


class RemoteException(ConnectorException):
    pass


class DecodeException(ConnectorException):
    pass
