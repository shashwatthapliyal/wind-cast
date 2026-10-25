from datetime import datetime, timezone
from statistics import mean

from app.models import ActualRecord, ForecastRecord, MatchedRecord
from app.services.forecast_selection import select_forecast


def normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return value.astimezone(timezone.utc)


def aggregate_half_hourly_actuals(actuals: list[ActualRecord]) -> list[ActualRecord]:
    """Average the two FUELHH half-hour values to WINDFOR's hourly periods."""
    by_hour: dict[datetime, dict[int, float | None]] = {}
    for actual in actuals:
        timestamp = normalize_timestamp(actual.startTime)
        if timestamp.minute not in (0, 30) or timestamp.second or timestamp.microsecond:
            raise ValueError("FUELHH startTime must identify a half-hour boundary")
        hour = timestamp.replace(minute=0)
        slots = by_hour.setdefault(hour, {})
        if timestamp.minute in slots:
            raise ValueError(f"duplicate FUELHH record for {timestamp.isoformat()}")
        slots[timestamp.minute] = actual.generation

    hourly = []
    for hour, slots in sorted(by_hour.items()):
        values = [slots.get(minute) for minute in (0, 30)]
        generation = mean(values) if all(value is not None for value in values) else None
        hourly.append(ActualRecord(startTime=hour, generation=generation, fuelType="WIND"))
    return hourly


def match_records(
    actuals: list[ActualRecord],
    forecasts: list[ForecastRecord],
    cutoff_minutes_before_delivery: int,
) -> list[MatchedRecord]:
    actual_by_time: dict[datetime, ActualRecord] = {}
    for actual in actuals:
        actual_by_time[normalize_timestamp(actual.startTime)] = actual
    forecast_by_time: dict[datetime, list[ForecastRecord]] = {}
    for forecast in forecasts:
        start = normalize_timestamp(forecast.startTime)
        forecast_by_time.setdefault(start, []).append(
            forecast.model_copy(update={"startTime": start, "publishTime": normalize_timestamp(forecast.publishTime)})
        )
    timestamps = sorted(set(actual_by_time) | set(forecast_by_time))
    result = []
    for timestamp in timestamps:
        selected = select_forecast(forecast_by_time.get(timestamp, []), timestamp, cutoff_minutes_before_delivery=cutoff_minutes_before_delivery)
        actual = actual_by_time.get(timestamp)
        error = (
            selected.generation - actual.generation
            if selected and actual and selected.generation is not None and actual.generation is not None
            else None
        )
        result.append(MatchedRecord(
            startTime=timestamp,
            publishTime=selected.publishTime if selected else None,
            forecastGeneration=selected.generation if selected else None,
            actualGeneration=actual.generation if actual else None,
            error=error,
            absoluteError=abs(error) if error is not None else None,
        ))
    return result
