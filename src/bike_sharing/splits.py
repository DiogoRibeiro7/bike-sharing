"""Explicit half-open calendar boundaries for training, validation and final testing."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from bike_sharing.data import DemandDataset, Observation, validate_observations, validate_timestamp


@dataclass(frozen=True, slots=True)
class StudySplit:
    """Train before validation_start; validate before test_start; test before test_end."""

    validation_start: datetime = datetime(2012, 7, 1)
    test_start: datetime = datetime(2012, 10, 1)
    test_end: datetime = datetime(2013, 1, 1)

    def __post_init__(self) -> None:
        for boundary in (self.validation_start, self.test_start, self.test_end):
            validate_timestamp(boundary)
        if not self.validation_start < self.test_start < self.test_end:
            raise ValueError(
                "split boundaries must satisfy validation_start < test_start < test_end"
            )

    def to_dict(self) -> dict[str, str]:
        """Serialize exact calendar boundaries without guessing a source timezone."""
        return {
            "validation_start": self.validation_start.isoformat(),
            "test_start": self.test_start.isoformat(),
            "test_end": self.test_end.isoformat(),
        }

    def validate_window(self, cutoff: datetime, horizon_hours: int) -> None:
        """Reject development windows outside validation, including test crossings."""
        validate_timestamp(cutoff)
        if type(horizon_hours) is not int or horizon_hours <= 0:
            raise ValueError("horizon_hours must be a positive integer")
        if (
            cutoff < self.validation_start
            or cutoff + timedelta(hours=horizon_hours) > self.test_start
        ):
            raise ValueError("development evaluation must stay within the validation partition")


DEFAULT_SPLIT = StudySplit()


@dataclass(frozen=True, slots=True)
class StudyPartitions:
    """Disjoint observed rows; absent calendar hours remain absent."""

    training: tuple[Observation, ...]
    validation: tuple[Observation, ...]
    test: tuple[Observation, ...]


def partition_dataset(dataset: DemandDataset, split: StudySplit = DEFAULT_SPLIT) -> StudyPartitions:
    """Assign observations to three ordered partitions and require support in each.

    The source must span the requested study end. Rows on or after test_end are
    outside this study and ignored. No outcomes are scored by this operation.
    """
    records = dataset.observations
    validate_observations(records)
    if split.test_end > records[-1].timestamp + timedelta(hours=1):
        raise ValueError("dataset does not span the requested test_end")
    partitions = StudyPartitions(
        training=tuple(item for item in records if item.timestamp < split.validation_start),
        validation=tuple(
            item for item in records if split.validation_start <= item.timestamp < split.test_start
        ),
        test=tuple(item for item in records if split.test_start <= item.timestamp < split.test_end),
    )
    if not partitions.training or not partitions.validation or not partitions.test:
        raise ValueError("training, validation and test partitions must all contain observations")
    return partitions
