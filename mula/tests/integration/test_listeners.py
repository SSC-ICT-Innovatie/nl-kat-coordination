import threading
import time
import unittest
from unittest import mock

import pika
from scheduler import clients, utils

from tests.mocks import listener


class RabbitMQTestCase(unittest.TestCase):
    DSN = "amqp://guest:guest@ci_rabbitmq:5672/%2Fkat"

    def setUp(self):
        self.listeners: list[clients.listeners.Listener] = []

        threading.excepthook = self.unhandled_exception

    def tearDown(self):
        for listener_ in self.listeners:
            listener_.stop()

    def unhandled_exception(self, args: threading.ExceptHookArgs) -> None:
        """An unhandled exception hook for threading."""
        for listener_ in self.listeners:
            listener_.stop()

    def test_shutdown(self):
        """Test that the listener stops when the stop method is called."""

        def test_func(body):
            pass

        stop_event = threading.Event()

        listener_ = listener.MockRabbitMQ(dsn=self.DSN, queue="test", func=test_func)
        self.listeners.append(listener_)

        # Run the listener
        thread = utils.ThreadRunner(
            name="MockRabbitMQ", target=listener_.listen, stop_event=stop_event, interval=0.01, daemon=False, loop=False
        )
        thread.start()

        # Make sure the listener is running
        self.assertTrue(thread.is_alive())

        # Call stop on the listener
        listener_.stop()

        max_wait = 5
        while thread.is_alive() and max_wait > 0:
            time.sleep(1)
            max_wait -= 1

        # Make sure the listener is stopped
        self.assertFalse(thread.is_alive())

    def test_shutdown_no_connection(self):
        """Test that the listener stops when the stop method is called without
        a connection."""

        def test_func(body):
            pass

        stop_event = threading.Event()

        listener_ = listener.MockRabbitMQ(dsn=self.DSN, queue="test", func=test_func)
        self.listeners.append(listener_)

        # Run the listener
        thread = utils.ThreadRunner(
            name="MockRabbitMQ", target=listener_.listen, stop_event=stop_event, interval=0.01, daemon=False, loop=False
        )
        thread.start()

        # Make sure the listener is running
        self.assertTrue(thread.is_alive())

        # Stop the listener
        listener_.connection = None
        listener_.stop()

        max_wait = 5
        while thread.is_alive() and max_wait > 0:
            time.sleep(1)
            max_wait -= 1

        # Make sure the listener is stopped
        self.assertFalse(thread.is_alive())

    @mock.patch("pika.adapters.blocking_connection.BlockingChannel.start_consuming")
    def test_start_consuming_exception(self, mock_start_consuming):
        """Test that the listener stops when an exception is raised in start_consuming."""

        def test_func(body):
            pass

        stop_event = threading.Event()

        listener_ = listener.MockRabbitMQ(dsn=self.DSN, queue="test", func=test_func)
        self.listeners.append(listener_)

        # Mocks
        # This will issue an unhandled_exception
        mock_start_consuming.side_effect = Exception("Test Exception")

        # Run the listener
        thread = utils.ThreadRunner(
            name="MockRabbitMQ", target=listener_.listen, stop_event=stop_event, interval=0.01, daemon=False, loop=False
        )
        thread.start()

        max_wait = 5
        while thread.is_alive() and max_wait > 0:
            time.sleep(1)
            max_wait -= 1

        # Make sure the listener stopped running
        for thread in threading.enumerate():
            if thread is threading.main_thread():
                continue

            self.assertFalse(thread.is_alive())

    def test_func_exception(self):
        """Test that the listener does NOT stop when an exception is raised in
        the func.

        Since the `func` is called evertime a message is received we can not
        determine that other message will be handled correctly or not. We want
        to make sure that exceptions are logged and the listener continues to
        run.
        """

        def test_func(body):
            raise Exception("Test Exception")

        stop_event = threading.Event()

        listener_ = listener.MockRabbitMQ(dsn=self.DSN, queue="test", func=test_func)
        self.listeners.append(listener_)

        # Run the listener
        thread = utils.ThreadRunner(
            name="MockRabbitMQ", target=listener_.listen, stop_event=stop_event, interval=0.01, daemon=False, loop=False
        )
        thread.start()

        # Make sure the listener is running
        self.assertTrue(thread.is_alive())

        # Act: send a message
        connection = pika.BlockingConnection(pika.URLParameters(self.DSN))
        channel = connection.channel()
        channel.queue_declare(queue="test", durable=True)
        channel.basic_publish(exchange="", routing_key="test", body="Test Message")
        channel.stop_consuming()
        channel.close()
        connection.close()

        max_wait = 5
        while thread.is_alive() and max_wait > 0:
            time.sleep(1)
            max_wait -= 1

        for thread in threading.enumerate():
            if thread is threading.main_thread():
                continue

            self.assertTrue(thread.is_alive())
