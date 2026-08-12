from .listeners import RabbitMQ


class RawData(RabbitMQ):
    """The RawData listener class that listens to the raw data queue and calls
    the function passed to it. This is used within the NormalizerScheduler.
    """

    pass
