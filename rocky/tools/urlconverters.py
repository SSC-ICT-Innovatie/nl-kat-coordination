from datetime import UTC, datetime

DATETIME_FORMAT = "%Y%m%dT%H%M%SZ"


class TemporalContextConverter:
    regex = r"now|at-\d{8}T\d{6}Z"

    def to_python(self, value):
        if value == "now":
            return None

        observed_at = value[len("at-") :]
        return datetime.strptime(observed_at, DATETIME_FORMAT).replace(tzinfo=UTC)

    def to_url(self, value):
        if isinstance(value, datetime):
            return f"at-{value.astimezone(UTC):{DATETIME_FORMAT}}"

        if value is None or value == "now":
            return "now"

        raise ValueError(value)


class OOIReferenceConverter:
    regex = r"[A-Za-z0-9]+\|.+"

    def to_python(self, value):
        return value

    def to_url(self, value):
        return str(value)  # we might be dealing with an OOI instance
