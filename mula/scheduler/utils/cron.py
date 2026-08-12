from datetime import datetime, timezone

from croniter import croniter


def next_run(expression: str, start_time: datetime | None = None) -> datetime:
    if start_time is None:
        start_time = datetime.now(timezone.utc)

    cron = croniter(expression, start_time)
    return cron.get_next(datetime)
