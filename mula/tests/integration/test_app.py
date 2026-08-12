import threading
import unittest
from types import SimpleNamespace
from unittest import mock

import scheduler
from scheduler import config, models, server, storage
from scheduler.storage import stores

from tests.factories import OrganisationFactory
from tests.mocks import MockKatalogusService


class AppTestCase(unittest.TestCase):
    def setUp(self):
        # Application Context
        self.mock_ctx = mock.patch("scheduler.context.AppContext").start()
        self.mock_ctx.config = config.settings.Settings()
        self.mock_ctx.services.katalogus = MockKatalogusService()

        # Database
        self.dbconn = storage.DBConn(str(self.mock_ctx.config.db_uri))
        self.dbconn.connect()
        models.Base.metadata.drop_all(self.dbconn.engine)
        models.Base.metadata.create_all(self.dbconn.engine)

        self.mock_ctx.datastores = SimpleNamespace(
            **{
                stores.TaskStore.name: stores.TaskStore(self.dbconn),
                stores.PriorityQueueStore.name: stores.PriorityQueueStore(self.dbconn),
            }
        )

        # App
        self.app = scheduler.App(self.mock_ctx)
        self.app.server = server.Server(self.mock_ctx, self.app.schedulers)

    def tearDown(self):
        self.app.shutdown()
        models.Base.metadata.drop_all(self.dbconn.engine)
        self.dbconn.engine.dispose()

    def test_shutdown(self):
        """Test that the app shuts down gracefully"""
        # Arrange
        self.mock_ctx.services.katalogus.organisations = {"org-1": OrganisationFactory(id="org-1")}
        self.app.start_schedulers()

        # Shutdown the app
        self.app.shutdown()

        # Assert that all threads have been stopped
        # for thread in self.app.threads:
        for t in threading.enumerate():
            if t is threading.main_thread():
                continue

            self.assertFalse(t.is_alive())
