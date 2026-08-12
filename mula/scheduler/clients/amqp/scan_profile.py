from .listeners import RabbitMQ


class ScanProfileMutation(RabbitMQ):
    """The ScanProfileMutation listener class that listens to the scan profile
    mutation queue and calls the function passed to it. This is used within the
    BoefjeScheduler.
    """

    pass
