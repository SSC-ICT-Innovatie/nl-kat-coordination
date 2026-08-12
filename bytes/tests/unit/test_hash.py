import datetime
from datetime import timezone
from unittest import TestCase

from bytes.models import HashingAlgorithm
from bytes.timestamping.hashing import hash_data
from tests.loading import get_raw_data


class HashTests(TestCase):
    def test_hash_same_data(self) -> None:
        dt = datetime.datetime(year=2022, month=1, day=1, hour=0, minute=0, second=0, tzinfo=timezone.utc)

        secure_hash = hash_data(data=get_raw_data(), datetime=dt)

        self.assertEqual(
            "sha512:bc4d1f0a71ba9bf2ab2b7520322f8e969c48d5ae99e84b4a60b850f61ce5b"
            "1e95e13f3ef6c43680fb03960f98799a92770e30591253784cc3213b194a73ea21d",
            secure_hash,
        )

        secure_hash = hash_data(data=get_raw_data(), datetime=dt)

        self.assertEqual(
            "sha512:bc4d1f0a71ba9bf2ab2b7520322f8e969c48d5ae99e84b4a60b850f61ce5b"
            "1e95e13f3ef6c43680fb03960f98799a92770e30591253784cc3213b194a73ea21d",
            secure_hash,
        )

    def test_hash_sha224(self) -> None:
        dt = datetime.datetime(year=2022, month=1, day=1, hour=0, minute=0, second=0, tzinfo=timezone.utc)

        secure_hash = hash_data(data=get_raw_data(), datetime=dt, hash_algo=HashingAlgorithm.SHA224)

        self.assertEqual("sha224:27154a1b6301ba1bde0b78cc28590e19b8f15c660f13885765cc3d44", secure_hash)

        secure_hash = hash_data(data=get_raw_data(), datetime=dt, hash_algo=HashingAlgorithm.SHA224)

        self.assertEqual("sha224:27154a1b6301ba1bde0b78cc28590e19b8f15c660f13885765cc3d44", secure_hash)
