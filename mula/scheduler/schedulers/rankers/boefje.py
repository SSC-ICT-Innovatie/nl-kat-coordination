from datetime import datetime, timedelta, timezone
from typing import Any

from .ranker import Ranker


class BoefjeRanker(Ranker):
    """The BoefjeRanker is a ranker that is used to rank tasks based on the
    procedure listed in the `rank()` method.
    """

    MAX_PRIORITY = 1000
    MAX_DAYS = 7

    def rank(self, obj: Any) -> int:
        """When a task hasn't run in a while it needs to be run sooner. We want
        a task to get a priority of 3 when `max_days` days are gone by, and
        thus it should have a lower bound of 3 for every task that has run past
        those`max_days`.

        3 has been chosen as a lower bound because new tasks that have not yet
        run before will get the priority of 2. And tasks created by the user
        (from rocky) will get a priority of 1.

        Before the end of those `max_days` we want to prioritize a task within
        a range from 3 to the maximum value of `max_priority`.
        """
        max_priority = self.MAX_PRIORITY
        max_days_in_seconds = self.MAX_DAYS * (60 * 60 * 24)
        grace_period = timedelta(seconds=self.ctx.config.pq_grace_period)

        # New tasks that have not yet run before
        if obj.latest_task is None or not obj.latest_task:
            return 2

        # Make sure that we don't have tasks that are still in the grace period.
        # Use total_seconds() rather than .seconds: the latter only returns the
        # H:M:S portion of a timedelta (0..86399) and drops the days, which
        # made both the `< 0` and `>= max_days_in_seconds` branches unreachable
        # and inverted the decay curve for tasks older than one day.
        time_since_grace_period = (
            (datetime.now(timezone.utc) - obj.latest_task.modified_at) - grace_period
        ).total_seconds()
        if time_since_grace_period < 0:
            return -1

        if time_since_grace_period >= max_days_in_seconds:
            return 3

        return int(3 + (max_priority - 3) * (1 - time_since_grace_period / max_days_in_seconds))


class BoefjeRankerTimeBased(Ranker):
    """A timed-based BoefjeRanker allows for a specific time to be set for the
    task to be ranked. You'll be able to rank jobs with a specific time
    element. Epoch time is used allows the score and used as the priority on
    the priority queue. This allows for time-based scheduling of jobs.
    """

    def rank(self, obj: Any) -> int:
        return int(obj.created_at.timestamp())
