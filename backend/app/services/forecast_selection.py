from datetime import datetime, timedelta

from app.models import ForecastRecord


def select_forecast(
    forecasts: list[ForecastRecord],
    delivery_time: datetime,
    cutoff: datetime | None = None,
    cutoff_minutes_before_delivery: int = 1440,
) -> ForecastRecord | None:
    applicable_cutoff = cutoff or delivery_time - timedelta(minutes=cutoff_minutes_before_delivery)
    eligible = [item for item in forecasts if item.startTime == delivery_time and item.publishTime <= applicable_cutoff]
    return max(eligible, key=lambda item: item.publishTime) if eligible else None
