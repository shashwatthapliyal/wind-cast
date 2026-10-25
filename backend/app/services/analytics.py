from collections import defaultdict
from datetime import datetime
from math import sqrt
from statistics import mean
from typing import Iterable

from app.models import Coverage, MatchedRecord, Metrics


def calculate_metrics(records: Iterable[MatchedRecord]) -> Metrics:
    valid = [r for r in records if r.error is not None and r.actualGeneration is not None and r.forecastGeneration is not None]
    if not valid:
        return Metrics(
            mae=None, rmse=None, bias=None, matchedPeriods=0,
            meanActualGeneration=None, meanForecastGeneration=None,
            maxAbsoluteError=None, maxAbsoluteErrorAt=None,
        )
    errors = [r.error for r in valid]
    largest = max(valid, key=lambda r: r.absoluteError or 0)
    return Metrics(
        mae=mean(abs(error) for error in errors),
        rmse=sqrt(mean(error * error for error in errors)),
        bias=mean(errors),
        matchedPeriods=len(valid),
        meanActualGeneration=mean(r.actualGeneration for r in valid),
        meanForecastGeneration=mean(r.forecastGeneration for r in valid),
        maxAbsoluteError=largest.absoluteError,
        maxAbsoluteErrorAt=largest.startTime,
    )


def coverage(
    expected_periods: int,
    actual_timestamps: set[datetime],
    forecast_timestamps: set[datetime],
    matched_periods: int,
) -> Coverage:
    missing_actual = max(expected_periods - len(actual_timestamps), 0)
    missing_forecast = max(expected_periods - len(forecast_timestamps), 0)
    return Coverage(
        expectedPeriods=expected_periods,
        observedActualPeriods=len(actual_timestamps),
        observedForecastPeriods=len(forecast_timestamps),
        matchedPeriods=matched_periods,
        missingActualPeriods=missing_actual,
        missingEligibleForecastPeriods=missing_forecast,
        coveragePercentage=(matched_periods / expected_periods * 100) if expected_periods else 0,
    )


def daily_metrics(records: Iterable[MatchedRecord]) -> list[dict]:
    grouped: dict[str, list[MatchedRecord]] = defaultdict(list)
    for record in records:
        grouped[record.startTime.date().isoformat()].append(record)
    return [{"date": day, "metrics": calculate_metrics(items).model_dump()} for day, items in sorted(grouped.items())]

