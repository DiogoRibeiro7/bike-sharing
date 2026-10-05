"""Small, auditable tools for aggregate hourly bike-rental forecasting."""

from bike_sharing.data import DemandDataset, Observation, load_dataset
from bike_sharing.forecasting import evaluate, forecast_baselines
from bike_sharing.splits import StudySplit, partition_dataset
from bike_sharing.study import (
    FrozenSelection,
    evaluate_test,
    read_selection,
    select_on_validation,
    select_rolling_on_validation,
)

__all__ = [
    "DemandDataset",
    "Observation",
    "StudySplit",
    "FrozenSelection",
    "evaluate",
    "forecast_baselines",
    "load_dataset",
    "partition_dataset",
    "select_on_validation",
    "select_rolling_on_validation",
    "evaluate_test",
    "read_selection",
]
__version__ = "0.4.0"
