import time

from scheduler.clients.amqp import listeners


class MockListener(listeners.Listener):
    def listen(self) -> None:
        time.sleep(1)

    def stop(self) -> None:
        pass


class MockRabbitMQ(listeners.RabbitMQ):
    pass
