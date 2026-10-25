from datetime import datetime, timezone

from app.models import MatchedRecord
from app.services.analytics import calculate_metrics


def record(error: float) -> MatchedRecord:
    return MatchedRecord(startTime=datetime(2026, 1, 1, tzinfo=timezone.utc), publishTime=None, forecastGeneration=10 + error, actualGeneration=10, error=error, absoluteError=abs(error))


def test_metrics():
    metrics = calculate_metrics([record(2), record(-1)])
    assert metrics.mae == 1.5
    assert round(metrics.rmse, 6) == round((5 / 2) ** 0.5, 6)
    assert metrics.bias == 0.5


def test_empty_metrics_are_null():
    assert calculate_metrics([]).mae is None
