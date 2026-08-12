import threading
import time
import unittest
from unittest import mock

from scheduler import clients, config, storage
from scheduler.utils import remove_trailing_slash

from tests.factories import PluginFactory


class BytesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.config = config.settings.Settings()
        self.service_bytes = clients.Bytes(
            host=remove_trailing_slash(str(self.config.host_bytes)),
            user=self.config.host_bytes_user,
            password=self.config.host_bytes_password,
            timeout=self.config.bytes_request_timeout,
            pool_connections=self.config.bytes_pool_connections,
            source="scheduler_test",
        )

    @unittest.skip
    def test_login(self):
        self.service_bytes.login()

        self.assertIsNotNone(self.service_bytes.headers)
        self.assertIsNotNone(self.service_bytes.headers.get("Authorization"))

    @unittest.skip
    def test_expired_token_refresh(self):
        self.service_bytes.get_last_run_boefje(boefje_id="boefje-1", input_ooi="ooi-1", organization_id="org-1")
        initial_token = id(self.service_bytes.headers.get("Authorization"))

        time.sleep(70)

        self.service_bytes.get_last_run_boefje(boefje_id="boefje-1", input_ooi="ooi-1", organization_id="org-1")
        refresh_token = id(self.service_bytes.headers.get("Authorization"))

        self.assertNotEqual(initial_token, refresh_token)


class KatalogusTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.config = config.settings.Settings()
        self.dbconn = storage.DBConn(str(self.config.db_uri))
        self.dbconn.connect()

        self.service_katalogus = clients.Katalogus(
            host=remove_trailing_slash(str(self.config.host_katalogus)),
            source="scheduler_test",
            timeout=self.config.katalogus_request_timeout,
            pool_connections=self.config.katalogus_pool_connections,
        )

    @mock.patch("scheduler.clients.http.external.katalogus.Katalogus.get_plugins_by_organisation")
    def test_get_new_boefjes_by_org_id(self, mock_get_plugins_by_organisation):
        # Mock
        mock_get_plugins_by_organisation.side_effect = [
            # First call
            [
                PluginFactory(id="plugin-1", type="boefje", enabled=True, consumes=["Hostname"]),
                PluginFactory(id="plugin-2", type="boefje", enabled=True, consumes=["Hostname"]),
                PluginFactory(id="plugin-3", type="boefje", enabled=False, consumes=["Hostname"]),
                PluginFactory(id="plugin-4", type="normalizer", enabled=True, consumes=["Hostname"]),
            ],
            # Second call
            [
                PluginFactory(id="plugin-1", type="boefje", enabled=True, consumes=["Hostname"]),
                PluginFactory(id="plugin-3", type="boefje", enabled=False, consumes=["Hostname"]),
                PluginFactory(id="plugin-4", type="normalizer", enabled=True, consumes=["Hostname"]),
                PluginFactory(id="plugin-5", type="boefje", enabled=True, consumes=["Hostname"]),
            ],
        ]

        # Act: First call we would expect 2 new boefjes
        new_boefjes = self.service_katalogus.get_new_boefjes_by_org_id("org-1")

        # Assert

        # Should have 1 organisation in cache
        self.assertEqual(len(self.service_katalogus.new_boefjes_cache), 1)
        self.assertIsNotNone(self.service_katalogus.new_boefjes_cache.get("org-1"))

        # Should have 2 new boefjes in cache
        self.assertEqual(len(self.service_katalogus.new_boefjes_cache.get("org-1")), 2)
        self.assertIsNotNone(self.service_katalogus.new_boefjes_cache.get("org-1").get("plugin-1"))
        self.assertIsNotNone(self.service_katalogus.new_boefjes_cache.get("org-1").get("plugin-2"))
        self.assertEqual(len(new_boefjes), 2)
        self.assertEqual(new_boefjes[0].id, "plugin-1")
        self.assertEqual(new_boefjes[1].id, "plugin-2")

        # Act: Second call we would expect 1 new boefje, and 1 removed boefje
        new_boefjes = self.service_katalogus.get_new_boefjes_by_org_id("org-1")

        # Assert

        # Should have 1 organisation in cache
        self.assertEqual(len(self.service_katalogus.new_boefjes_cache), 1)
        self.assertIsNotNone(self.service_katalogus.new_boefjes_cache.get("org-1"))

        # Should have 2 new boefjes in cache
        self.assertEqual(len(self.service_katalogus.new_boefjes_cache.get("org-1")), 2)
        self.assertIsNotNone(self.service_katalogus.new_boefjes_cache.get("org-1").get("plugin-1"))
        self.assertIsNone(self.service_katalogus.new_boefjes_cache.get("org-1").get("plugin-2"))
        self.assertIsNotNone(self.service_katalogus.new_boefjes_cache.get("org-1").get("plugin-5"))

        self.assertEqual(len(new_boefjes), 1)
        self.assertEqual(new_boefjes[0].id, "plugin-5")

    @mock.patch("scheduler.clients.http.external.katalogus.Katalogus.get_plugins_by_organisation")
    def test_new_boefjes_cache_thread_safety(self, mock_get_plugins_by_organisation):
        mock_get_plugins_by_organisation.side_effect = [
            [
                PluginFactory(id="plugin-1", type="boefje", enabled=True, consumes=["Hostname"]),
                PluginFactory(id="plugin-2", type="boefje", enabled=True, consumes=["Hostname"]),
                PluginFactory(id="plugin-3", type="boefje", enabled=False, consumes=["Hostname"]),
                PluginFactory(id="plugin-4", type="normalizer", enabled=True, consumes=["Hostname"]),
            ]
        ]

        event = threading.Event()

        def write_to_cache(event):
            with self.service_katalogus.new_boefjes_cache_lock:
                event.set()

                # We simulate a long running task and thread 2 would
                # potentially start before this task is done
                time.sleep(5)

                self.service_katalogus.new_boefjes_cache["org-1"] = {
                    "plugin-5": PluginFactory(id="plugin-5", type="boefje", enabled=True, consumes=["Hostname"])
                }

        thread1 = threading.Thread(target=write_to_cache, args=(event,))
        thread2 = threading.Thread(target=self.service_katalogus.get_new_boefjes_by_org_id, args=("org-1",))

        thread1.start()

        # Wait for thread 1 to set the event before starting thread 2
        event.wait()
        thread2.start()

        thread1.join()
        thread2.join()

        self.assertEqual(len(self.service_katalogus.new_boefjes_cache.get("org-1")), 2)
