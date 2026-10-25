from datetime import datetime, timedelta, timezone

from app.models import ForecastRecord
from app.services.forecast_selection import select_forecast


def test_latest_eligible_vintage_is_selected():
    delivery = datetime(2026, 1, 2, tzinfo=timezone.utc)
    forecasts = [
        ForecastRecord(startTime=delivery, publishTime=delivery - timedelta(hours=30), generation=1),
        ForecastRecord(startTime=delivery, publishTime=delivery - timedelta(hours=20), generation=2),
        ForecastRecord(startTime=delivery, publishTime=delivery - timedelta(hours=2), generation=3),
    ]
    assert select_forecast(forecasts, delivery, cutoff_minutes_before_delivery=24 * 60).generation == 1
