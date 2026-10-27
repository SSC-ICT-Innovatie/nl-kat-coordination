from datetime import UTC, datetime

from croniter import croniter


def next_run(expression: str, start_time: datetime | None = None) -> datetime:
    if start_time is None:
        start_time = datetime.now(UTC)

    cron = croniter(expression, start_time)
    return cron.get_next(datetime)
