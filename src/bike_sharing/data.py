"""Validate the historical CSV without changing its bytes or filling absent hours."""

import csv
import hashlib
import io
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

REQUIRED_COLUMNS = frozenset({"Date", "Hour", "Total Users", "Casual Users", "Registered Users"})


def validate_timestamp(timestamp: datetime) -> None:
    """Require a naive, hourly timestamp in the dataset's unresolved local calendar."""
    if not isinstance(timestamp, datetime):
        raise TypeError("timestamp must be a datetime")
    if timestamp.tzinfo is not None:
        raise ValueError("timestamps must be timezone-naive; source timezone is not verified")
    if timestamp.minute or timestamp.second or timestamp.microsecond:
        raise ValueError("timestamps must fall on an exact hour")


@dataclass(frozen=True, slots=True)
class Observation:
    """An observed total rental count at one hourly calendar timestamp."""

    timestamp: datetime
    count: int

    def __post_init__(self) -> None:
        validate_timestamp(self.timestamp)
        if type(self.count) is not int:
            raise TypeError("count must be an integer, not a boolean or float")
        if self.count < 0:
            raise ValueError("count must be nonnegative")


@dataclass(frozen=True, slots=True)
class DemandDataset:
    """Validated observations plus the identity of the exact input bytes."""

    observations: tuple[Observation, ...]
    sha256: str
    source_name: str


def load_dataset(path: Path) -> DemandDataset:
    """Read and sort the legacy CSV, rejecting ambiguous or inconsistent records.

    Extra named columns are ignored. Counts are checked against their two
    components, but those components never become forecasting predictors.
    Missing calendar hours remain missing, rather than being filled with zeros.
    """
    raw = path.read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    names = reader.fieldnames
    if not names or len(set(names)) != len(names):
        raise ValueError("CSV header must contain unique column names")
    missing = REQUIRED_COLUMNS.difference(names)
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")
    observations: list[Observation] = []
    seen: set[datetime] = set()
    for row in reader:
        line = reader.line_num
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"CSV row {line}: number of fields does not match the header")
        try:
            hour = int(row["Hour"])
            if not 0 <= hour <= 23:
                raise ValueError("Hour must be between 0 and 23")
            timestamp = datetime.strptime(row["Date"], "%m/%d/%Y") + timedelta(hours=hour)
            counts = [
                int(row[name]) for name in ("Total Users", "Casual Users", "Registered Users")
            ]
            if any(count < 0 for count in counts):
                raise ValueError("rental counts must be nonnegative")
            if counts[0] != counts[1] + counts[2]:
                raise ValueError("Total Users must equal Casual Users plus Registered Users")
        except ValueError as exc:
            raise ValueError(f"CSV row {line}: {exc}") from exc
        if timestamp in seen:
            raise ValueError(f"CSV row {line}: duplicate timestamp {timestamp.isoformat()}")
        seen.add(timestamp)
        observations.append(Observation(timestamp, counts[0]))
    if not observations:
        raise ValueError("CSV contains no observations")
    return DemandDataset(
        observations=tuple(sorted(observations, key=lambda item: item.timestamp)),
        sha256=hashlib.sha256(raw).hexdigest(),
        source_name=path.name,
    )


def validate_observations(observations: Sequence[Observation]) -> None:
    """Reject empty, duplicate or out-of-order observations at API boundaries."""
    if not observations:
        raise ValueError("at least one observation is required")
    if any(
        left.timestamp >= right.timestamp
        for left, right in zip(observations, observations[1:], strict=False)
    ):
        raise ValueError("observations must have unique, strictly increasing timestamps")


def coverage(observations: Sequence[Observation]) -> dict[str, int | str]:
    """Describe observed coverage between the first and last supplied timestamps."""
    validate_observations(observations)
    first, last = observations[0].timestamp, observations[-1].timestamp
    expected = int((last - first).total_seconds() // 3600) + 1
    return {
        "first_timestamp": first.isoformat(),
        "last_timestamp": last.isoformat(),
        "observations": len(observations),
        "calendar_hours": expected,
        "absent_calendar_hours": expected - len(observations),
    }
