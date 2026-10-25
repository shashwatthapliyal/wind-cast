from datetime import datetime, timezone
import asyncio

from fastapi.testclient import TestClient
import pytest
from fastapi import HTTPException

from app import main
from app.main import app
from app.models import ActualRecord, ForecastRecord
from app.services.repository import DataRepository
from app.services.elexon_client import ElexonClientError


def sample_data():
    actuals = [
        ActualRecord(startTime=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), generation=0),
        ActualRecord(startTime=datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc), generation=10),
    ]
    forecasts = [
        ForecastRecord(startTime=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), publishTime=datetime(2025, 12, 31, tzinfo=timezone.utc), generation=0),
        ForecastRecord(startTime=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), publishTime=datetime(2026, 1, 1, tzinfo=timezone.utc), generation=9),
        ForecastRecord(startTime=datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc), publishTime=datetime(2025, 12, 31, tzinfo=timezone.utc), generation=10),
    ]
    return actuals, forecasts, datetime(2026, 2, 1, tzinfo=timezone.utc)


def install_data(monkeypatch):
    async def fake_load_data(force_refresh=False):
        return sample_data()

    monkeypatch.setattr(main, "load_data", fake_load_data)


def test_health_response_schema():
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_summary_and_accuracy_use_selected_date_range(monkeypatch):
    install_data(monkeypatch)
    client = TestClient(app)
    params = {"start_date": "2026-01-01", "end_date": "2026-01-01"}

    summary = client.get("/api/summary", params=params)
    accuracy = client.get("/api/accuracy", params=params)

    assert summary.status_code == accuracy.status_code == 200
    assert summary.json()["coverage"]["expectedPeriods"] == 24
    assert summary.json()["metrics"]["matchedPeriods"] == 2
    assert accuracy.json()["coverage"]["expectedPeriods"] == 24
    assert accuracy.json()["overall"]["mae"] == 0
    assert len(accuracy.json()["daily"]) == 1


def test_forecast_list_vintages_and_pagination(monkeypatch):
    install_data(monkeypatch)
    client = TestClient(app)
    records = client.get("/api/forecasts", params={"start_date": "2026-01-01", "end_date": "2026-01-01", "limit": 1})
    vintages = client.get("/api/forecasts/vintages", params={"delivery_date": "2026-01-01"})

    assert records.status_code == 200
    assert len(records.json()) == 1
    assert records.json()[0]["actualGeneration"] == 0
    assert vintages.status_code == 200
    assert len(vintages.json()) == 3
    assert vintages.json()[0]["publishTime"] == "2025-12-31T00:00:00Z"


def test_data_quality_and_csv_preserve_zero_values(monkeypatch):
    install_data(monkeypatch)
    client = TestClient(app)
    params = {"start_date": "2026-01-01", "end_date": "2026-01-01"}

    quality = client.get("/api/data-quality", params=params)
    csv_response = client.get("/api/export/csv", params=params)

    assert quality.status_code == 200
    assert quality.json()["expectedPeriods"] == 24
    assert quality.json()["missingActualPeriods"] == 22
    assert csv_response.status_code == 200
    assert ",0.0,0.0,0.0,0.0\r\n" in csv_response.text


def test_refresh_forces_backend_data_load(monkeypatch):
    calls = []

    async def fake_load_data(force_refresh=False):
        calls.append(force_refresh)
        return sample_data()

    monkeypatch.setattr(main, "load_data", fake_load_data)
    response = TestClient(app).post("/api/refresh")

    assert response.status_code == 200
    assert calls == [True]
    assert response.json()["status"] == "refreshed"
    assert response.json()["forecastRecords"] == 3


def test_invalid_ranges_and_vintage_dates_are_rejected(monkeypatch):
    install_data(monkeypatch)
    client = TestClient(app)

    assert client.get("/api/forecasts?start_date=2025-12-01").status_code == 422
    assert client.get("/api/forecasts?limit=0").status_code == 422
    assert client.get("/api/forecasts/vintages?delivery_date=2026-02-01").status_code == 422
    assert client.get("/api/forecasts/vintages?delivery_date=2026-01-02").status_code == 404
    assert client.get("/api/does-not-exist").status_code == 404


@pytest.mark.asyncio
async def test_load_data_normalizes_source_records_and_persists_raw_values(tmp_path, monkeypatch):
    calls = []

    class FakeElexonClient:
        def __init__(self, *_args):
            pass

        async def fetch_fuelhh(self, start, end, fuel_type="WIND"):
            calls.append(("FUELHH", start.isoformat(), end.isoformat(), fuel_type))
            return [
                {"startTime": "2026-01-01T00:00:00Z", "generation": 10, "fuelType": "WIND"},
                {"startTime": "2026-01-01T00:30:00Z", "generation": 14, "fuelType": "WIND"},
            ]

        async def fetch_windfor(self, publish_from, publish_to):
            calls.append(("WINDFOR", publish_from.isoformat(), publish_to.isoformat()))
            return [{
                "startTime": "2026-01-01T00:00:00Z",
                "publishTime": "2025-12-31T00:00:00Z",
                "generation": 12,
            }]

    monkeypatch.setattr(main, "ElexonClient", FakeElexonClient)
    monkeypatch.setattr(main, "repository", DataRepository(tmp_path))
    monkeypatch.setattr(main, "_initial_refresh_done", False)

    actuals, forecasts, retrieved = await main.load_data(force_refresh=True)

    assert actuals[0].generation == 12
    assert forecasts[0].generation == 12
    assert retrieved is not None
    assert calls[0] == ("FUELHH", "2026-01-01", "2026-01-31", "WIND")
    assert calls[1][0] == "WINDFOR"
    assert len(DataRepository(tmp_path).load("actuals")[0]) == 2


def test_unavailable_upstream_returns_service_unavailable(tmp_path, monkeypatch):
    class OfflineElexonClient:
        def __init__(self, *_args):
            pass

        async def fetch_fuelhh(self, *_args, **_kwargs):
            raise ElexonClientError("Could not connect to Elexon for FUELHH")

        async def fetch_windfor(self, *_args, **_kwargs):
            raise ElexonClientError("Could not connect to Elexon for WINDFOR")

    monkeypatch.setattr(main, "ElexonClient", OfflineElexonClient)
    monkeypatch.setattr(main, "repository", DataRepository(tmp_path))
    monkeypatch.setattr(main, "_initial_refresh_done", False)

    response = TestClient(app).get("/api/summary")

    assert response.status_code == 503
    assert "Could not connect to Elexon" in response.json()["detail"]


@pytest.mark.asyncio
async def test_parallel_loads_do_not_repeat_failed_upstream_requests(tmp_path, monkeypatch):
    calls = []

    class OfflineElexonClient:
        def __init__(self, *_args):
            pass

        async def fetch_fuelhh(self, *_args, **_kwargs):
            calls.append("FUELHH")
            raise ElexonClientError("Could not connect to Elexon for FUELHH")

        async def fetch_windfor(self, *_args, **_kwargs):
            calls.append("WINDFOR")
            raise ElexonClientError("Could not connect to Elexon for WINDFOR")

    monkeypatch.setattr(main, "ElexonClient", OfflineElexonClient)
    monkeypatch.setattr(main, "repository", DataRepository(tmp_path))
    monkeypatch.setattr(main.settings, "refresh_cache", False)
    monkeypatch.setattr(main, "_initial_refresh_done", False)
    monkeypatch.setattr(main, "_last_data_error", None)

    results = await asyncio.gather(*(main.load_data() for _ in range(3)), return_exceptions=True)

    assert calls.count("FUELHH") == 1
    assert calls.count("WINDFOR") == 1
    assert all(isinstance(result, HTTPException) and result.status_code == 503 for result in results)
