from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _utc_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return value.astimezone(timezone.utc)


class ForecastRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    startTime: datetime
    publishTime: datetime
    generation: float | None = Field(default=None, ge=0)

    @field_validator("startTime", "publishTime")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _utc_timestamp(value)


class ActualRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    startTime: datetime
    generation: float | None = Field(default=None, ge=0)
    fuelType: str = "WIND"

    @field_validator("startTime")
    @classmethod
    def normalize_start_time(cls, value: datetime) -> datetime:
        return _utc_timestamp(value)


class MatchedRecord(BaseModel):
    startTime: datetime
    publishTime: datetime | None
    forecastGeneration: float | None
    actualGeneration: float | None
    error: float | None
    absoluteError: float | None


class Metrics(BaseModel):
    mae: float | None
    rmse: float | None
    bias: float | None
    matchedPeriods: int
    meanActualGeneration: float | None
    meanForecastGeneration: float | None
    maxAbsoluteError: float | None
    maxAbsoluteErrorAt: datetime | None


class Coverage(BaseModel):
    expectedPeriods: int
    observedActualPeriods: int
    observedForecastPeriods: int
    matchedPeriods: int
    missingActualPeriods: int
    missingEligibleForecastPeriods: int
    coveragePercentage: float


class SummaryResponse(BaseModel):
    analysisStart: date
    analysisEnd: date
    decisionCutoffPolicy: str
    metrics: Metrics
    coverage: Coverage
    latestSuccessfulRetrieval: datetime | None


class AccuracyResponse(BaseModel):
    overall: Metrics
    coverage: Coverage
    daily: list[dict[str, Any]]


class HealthResponse(BaseModel):
    status: str
    service: str
    cacheStatus: str

