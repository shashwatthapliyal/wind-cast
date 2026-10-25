from datetime import datetime, timezone

from app.models import ActualRecord, ForecastRecord
from app.services.matching import aggregate_half_hourly_actuals, match_records


def test_timezone_normalization_and_missing_values():
    actual = ActualRecord(startTime=datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc), generation=5)
    forecast = ForecastRecord(startTime=datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc), publishTime=datetime(2025, 12, 31, tzinfo=timezone.utc), generation=7)
    result = match_records([actual], [forecast], 0)
    assert result[0].error == 2


def test_half_hourly_actuals_are_averaged_to_hourly_periods():
    actuals = [
        ActualRecord(startTime=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), generation=2),
        ActualRecord(startTime=datetime(2026, 1, 1, 0, 30, tzinfo=timezone.utc), generation=4),
        ActualRecord(startTime=datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc), generation=8),
    ]

    hourly = aggregate_half_hourly_actuals(actuals)

    assert [record.generation for record in hourly] == [3, None]
    assert [record.startTime for record in hourly] == [
        datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc),
    ]


def test_source_timestamps_are_normalized_to_utc():
    actual = ActualRecord(startTime=datetime.fromisoformat("2026-01-01T02:00:00+02:00"), generation=5)
    assert actual.startTime == datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
