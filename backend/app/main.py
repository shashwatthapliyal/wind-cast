import asyncio
import csv
import io
import logging
from datetime import date, datetime, time, timedelta, timezone
from time import monotonic

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.models import ActualRecord, ForecastRecord, HealthResponse, SummaryResponse, AccuracyResponse
from app.services.analytics import calculate_metrics, coverage, daily_metrics
from app.services.elexon_client import ElexonClient, ElexonClientError
from app.services.matching import aggregate_half_hourly_actuals, match_records
from app.services.repository import DataRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
repository = DataRepository(settings.cache_path)
_data_lock = asyncio.Lock()
_initial_refresh_done = False
_last_data_error: tuple[float, str] | None = None
_failure_cooldown_seconds = 10


def parse_period(start_date: date | None, end_date: date | None) -> tuple[date, date]:
    start = start_date or date.fromisoformat(settings.analysis_start)
    end = end_date or date.fromisoformat(settings.analysis_end)
    configured_start = date.fromisoformat(settings.analysis_start)
    configured_end = date.fromisoformat(settings.analysis_end)
    if start > end or start < configured_start or end > configured_end:
        raise HTTPException(422, f"Date range must be within {configured_start.isoformat()} to {configured_end.isoformat()}")
    return start, end


def expected_periods(start: date, end: date) -> int:
    """Return UTC hourly comparison periods for an inclusive date range."""
    return ((end - start).days + 1) * 24


def _cache_overlaps(records: list[dict], start: date, end: date) -> bool:
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("startTime"), str):
            continue
        try:
            timestamp = datetime.fromisoformat(record["startTime"].replace("Z", "+00:00"))
        except ValueError:
            continue
        if timestamp.tzinfo and start <= timestamp.astimezone(timezone.utc).date() <= end:
            return True
    return False


async def _read_cache(name: str):
    try:
        return repository.load(name)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.warning("Ignoring invalid %s cache: %s", name, exc)
        return None


async def load_data(force_refresh: bool = False) -> tuple[list[ActualRecord], list[ForecastRecord], datetime | None]:
    global _initial_refresh_done, _last_data_error
    start = date.fromisoformat(settings.analysis_start)
    end = date.fromisoformat(settings.analysis_end)

    async with _data_lock:
        if (
            not force_refresh
            and _last_data_error is not None
            and monotonic() - _last_data_error[0] < _failure_cooldown_seconds
        ):
            raise HTTPException(503, f"Historical Elexon data is unavailable: {_last_data_error[1]}")
        refresh_on_first_load = settings.refresh_cache and not _initial_refresh_done
        actual_cached = await _read_cache("actuals")
        forecast_cached = await _read_cache("forecasts")
        cache_is_usable = (
            actual_cached is not None
            and forecast_cached is not None
            and (not actual_cached[0] or _cache_overlaps(actual_cached[0], start, end))
            and (not forecast_cached[0] or _cache_overlaps(forecast_cached[0], start, end))
        )
        if cache_is_usable and not force_refresh and not refresh_on_first_load:
            try:
                actuals = [ActualRecord.model_validate(row) for row in actual_cached[0]]
                forecasts = [ForecastRecord.model_validate(row) for row in forecast_cached[0]]
                retrieved = max(actual_cached[1], forecast_cached[1])
                return aggregate_half_hourly_actuals(actuals), forecasts, retrieved
            except (ValueError, TypeError) as exc:
                logger.warning("Ignoring incompatible Elexon cache: %s", exc)

        client = ElexonClient(settings.elexon_base_url, settings.request_timeout_seconds, settings.max_retries)
        publication_from = datetime.combine(start, time.min, tzinfo=timezone.utc) - timedelta(
            minutes=settings.decision_cutoff_minutes_before_delivery,
            days=1,
        )
        publication_to = datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc)
        try:
            actual_raw, forecast_raw = await asyncio.gather(
                client.fetch_fuelhh(start, end, fuel_type="WIND"),
                client.fetch_windfor(publication_from, publication_to),
            )
            actuals = [ActualRecord.model_validate(row) for row in actual_raw if row.get("fuelType") == "WIND"]
            forecasts = [ForecastRecord.model_validate(row) for row in forecast_raw]
            retrieved = datetime.now(timezone.utc)
            repository.save("actuals", [record.model_dump(mode="json") for record in actuals])
            repository.save("forecasts", [record.model_dump(mode="json") for record in forecasts])
            _initial_refresh_done = True
            _last_data_error = None
            return aggregate_half_hourly_actuals(actuals), forecasts, retrieved
        except (ElexonClientError, ValueError, TypeError, OSError) as exc:
            _last_data_error = (monotonic(), str(exc))
            raise HTTPException(503, f"Historical Elexon data is unavailable: {exc}") from exc


async def build_records(start_date: date | None, end_date: date | None):
    start, end = parse_period(start_date, end_date)
    actuals, forecasts, retrieved = await load_data()
    records = match_records(actuals, forecasts, settings.decision_cutoff_minutes_before_delivery)
    return [record for record in records if start <= record.startTime.date() <= end], retrieved


@app.get("/api/health", response_model=HealthResponse)
async def health():
    cache_files = [settings.cache_path / "actuals.json", settings.cache_path / "forecasts.json"]
    cache_status = "available" if all(path.is_file() for path in cache_files) else "not_loaded"
    return HealthResponse(status="ok", service=settings.app_name, cacheStatus=cache_status)


@app.post("/api/refresh")
async def refresh_data():
    actuals, forecasts, retrieved = await load_data(force_refresh=True)
    return {
        "status": "refreshed",
        "actualRecords": len(actuals),
        "forecastRecords": len(forecasts),
        "retrievedAt": retrieved,
    }


@app.get("/api/summary", response_model=SummaryResponse)
async def summary(start_date: date | None = None, end_date: date | None = None):
    start, end = parse_period(start_date, end_date)
    records, retrieved = await build_records(start, end)
    expected = expected_periods(start, end)
    actual_times = {record.startTime for record in records if record.actualGeneration is not None}
    forecast_times = {record.startTime for record in records if record.forecastGeneration is not None}
    matched = [record for record in records if record.error is not None]
    return SummaryResponse(
        analysisStart=start,
        analysisEnd=end,
        decisionCutoffPolicy=f"{settings.decision_cutoff_minutes_before_delivery} minutes before delivery; configurable assumption, not an official market deadline",
        metrics=calculate_metrics(records),
        coverage=coverage(expected, actual_times, forecast_times, len(matched)),
        latestSuccessfulRetrieval=retrieved,
    )


@app.get("/api/forecasts")
async def forecasts(
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(2000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
):
    records, _ = await build_records(start_date, end_date)
    return records[offset:offset + limit]


@app.get("/api/accuracy", response_model=AccuracyResponse)
async def accuracy(start_date: date | None = None, end_date: date | None = None):
    start, end = parse_period(start_date, end_date)
    records, _ = await build_records(start, end)
    metrics = calculate_metrics(records)
    return AccuracyResponse(
        overall=metrics,
        coverage=coverage(
            expected_periods(start, end),
            {record.startTime for record in records if record.actualGeneration is not None},
            {record.startTime for record in records if record.forecastGeneration is not None},
            metrics.matchedPeriods,
        ),
        daily=daily_metrics(records),
    )


@app.get("/api/forecasts/vintages")
async def vintages(delivery_date: date):
    parse_period(delivery_date, delivery_date)
    _, forecasts, _ = await load_data()
    values = [record for record in forecasts if record.startTime.date() == delivery_date]
    if not values:
        raise HTTPException(404, "No forecast vintages available for delivery date")
    return sorted(values, key=lambda record: record.publishTime)


@app.get("/api/data-quality")
async def data_quality(start_date: date | None = None, end_date: date | None = None):
    start, end = parse_period(start_date, end_date)
    records, retrieved = await build_records(start, end)
    expected = expected_periods(start, end)
    observed_actuals = sum(record.actualGeneration is not None for record in records)
    observed_forecasts = sum(record.forecastGeneration is not None for record in records)
    return {
        "expectedPeriods": expected,
        "observedPeriods": len(records),
        "missingActualPeriods": max(expected - observed_actuals, 0),
        "missingEligibleForecastPeriods": max(expected - observed_forecasts, 0),
        "retrievedAt": retrieved,
        "status": "ok" if observed_actuals == expected and observed_forecasts == expected else "incomplete",
    }


@app.get("/api/export/csv")
async def export_csv(start_date: date | None = None, end_date: date | None = None):
    records, _ = await build_records(start_date, end_date)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["startTime", "publishTime", "forecastGeneration", "actualGeneration", "error", "absoluteError"])
    for record in records:
        writer.writerow([
            record.startTime.isoformat(),
            record.publishTime.isoformat() if record.publishTime else "",
            record.forecastGeneration if record.forecastGeneration is not None else "",
            record.actualGeneration if record.actualGeneration is not None else "",
            record.error if record.error is not None else "",
            record.absoluteError if record.absoluteError is not None else "",
        ])
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=wind-forecast.csv"},
    )
