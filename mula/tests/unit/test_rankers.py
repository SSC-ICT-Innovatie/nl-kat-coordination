from datetime import datetime, timedelta, timezone
from unittest import TestCase, mock

from scheduler.schedulers.rankers.boefje import BoefjeRanker, BoefjeRankerTimeBased
from scheduler.schedulers.rankers.normalizer import NormalizerRanker


class BoefjeRankerTestCase(TestCase):
    """Isolated unit tests for BoefjeRanker. The ranker is currently only
    exercised end-to-end via the simulation suite, which makes priority
    regressions hard to attribute. These tests pin the documented behaviour
    of `rank()` so future refactors can't silently break it.
    """

    def setUp(self):
        self.ctx = mock.MagicMock()
        self.ctx.config.pq_grace_period = 0  # easier to reason about boundaries
        self.ranker = BoefjeRanker(ctx=self.ctx)

    def _obj_with_latest_task(self, modified_at: datetime) -> mock.Mock:
        latest_task = mock.Mock()
        latest_task.modified_at = modified_at
        obj = mock.Mock()
        obj.latest_task = latest_task
        return obj

    def test_rank_new_task_returns_2(self):
        obj = mock.Mock()
        obj.latest_task = None
        self.assertEqual(2, self.ranker.rank(obj))

    def test_rank_falsy_latest_task_returns_2(self):
        # The implementation also accepts `not obj.latest_task` for the new-task case.
        obj = mock.Mock()
        obj.latest_task = False
        self.assertEqual(2, self.ranker.rank(obj))

    def test_rank_task_just_ran_is_close_to_max_priority(self):
        # A task that just ran (no time elapsed) should sit near the top of the
        # 3..MAX_PRIORITY range. Allow a small tolerance for sub-second jitter.
        recent = datetime.now(timezone.utc) - timedelta(seconds=1)
        score = self.ranker.rank(self._obj_with_latest_task(recent))
        self.assertGreater(score, BoefjeRanker.MAX_PRIORITY - 5)
        self.assertLessEqual(score, BoefjeRanker.MAX_PRIORITY)

    def test_rank_task_older_than_max_days_returns_3(self):
        old = datetime.now(timezone.utc) - timedelta(days=BoefjeRanker.MAX_DAYS + 1)
        self.assertEqual(3, self.ranker.rank(self._obj_with_latest_task(old)))

    def test_rank_task_within_grace_period_returns_minus_one(self):
        # Set a grace period of 1 hour and a latest_task that ran 1 minute ago.
        # The grace period has not elapsed, so the ranker should signal "skip".
        self.ctx.config.pq_grace_period = 3600
        recent = datetime.now(timezone.utc) - timedelta(minutes=1)
        self.assertEqual(-1, self.ranker.rank(self._obj_with_latest_task(recent)))

    def test_rank_decays_monotonically_over_time(self):
        # Two tasks where one ran more recently than the other should rank the
        # recent one higher (= larger priority number) than the older one.
        # Catches sign flips and .seconds-truncation regressions.
        now = datetime.now(timezone.utc)
        recent = self.ranker.rank(self._obj_with_latest_task(now - timedelta(hours=1)))
        older = self.ranker.rank(self._obj_with_latest_task(now - timedelta(days=3)))
        self.assertGreater(recent, older)


class BoefjeRankerTimeBasedTestCase(TestCase):
    def test_rank_returns_creation_epoch(self):
        ranker = BoefjeRankerTimeBased(ctx=mock.MagicMock())
        obj = mock.Mock()
        obj.created_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(int(obj.created_at.timestamp()), ranker.rank(obj))


class NormalizerRankerTestCase(TestCase):
    """The NormalizerRanker prioritises older raw files so they get processed
    first. The score is the boefje_meta.ended_at epoch — older = lower number =
    higher priority on the min-heap PQ.
    """

    def test_rank_returns_boefje_meta_ended_at_epoch(self):
        ranker = NormalizerRanker(ctx=mock.MagicMock())
        obj = mock.Mock()
        obj.raw_data.boefje_meta.ended_at = datetime(2026, 4, 11, 9, 30, 0, tzinfo=timezone.utc)
        self.assertEqual(int(obj.raw_data.boefje_meta.ended_at.timestamp()), ranker.rank(obj))

    def test_rank_orders_older_raws_lower(self):
        ranker = NormalizerRanker(ctx=mock.MagicMock())
        older = mock.Mock()
        older.raw_data.boefje_meta.ended_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        newer = mock.Mock()
        newer.raw_data.boefje_meta.ended_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
        self.assertLess(ranker.rank(older), ranker.rank(newer))
