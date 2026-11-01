import unittest
from datetime import UTC, datetime, timedelta

from scheduler import utils


class ExpiringDictTestCase(unittest.TestCase):
    def test_lifetime_expired(self):
        ed = utils.ExpiringDict(lifetime=1, start_time=datetime.now(UTC) - timedelta(seconds=2))
        ed["a"] = 1
        with self.assertRaises(utils.ExpiredError):
            ed.get("a")

    def test_lifetime_not_expired(self):
        ed = utils.ExpiringDict()
        ed["a"] = 1

        self.assertEqual(1, ed.get("a"))

    def test_toggle_expire(self):
        ed = utils.ExpiringDict()
        ed["a"] = 1

        ed.expiration_time = datetime.now(UTC) - timedelta(seconds=2)

        ed.expiration_enabled = False

        self.assertEqual(1, ed.get("a"))

        ed.expiration_enabled = True
        ed.expiration_time = datetime.now(UTC) - timedelta(seconds=2)

        with self.assertRaises(utils.ExpiredError):
            ed.get("a")
