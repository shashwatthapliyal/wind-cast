# Wind Forecast Intelligence backend

FastAPI backend for comparing Elexon FUELHH national WIND actual generation with WINDFOR forecast vintages for January 2026. FUELHH observations are half-hourly while WINDFOR values are hourly, so the backend averages each complete pair of half-hour actuals to an hourly mean before comparison. It uses UTC internally, keeps forecast publication history, and selects the latest publication at or before a configurable decision cutoff (default: 24 hours before delivery). This is an explicit analytical assumption, not an official market deadline.

## Run locally

```powershell
cd backend
py -m venv .venv
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Run tests with the project virtual environment's `python -m pytest -q`.

## Docker

```powershell
docker build -t wind-forecast-backend .
docker run --env-file .env -p 8000:8000 wind-forecast-backend
```

The first data request retrieves and caches January actuals and forecast publications from the decision window through the end of January under `data/cache`. Pressing **Refresh data** calls `POST /api/refresh` to retrieve them again. `WIND_REFRESH_CACHE=true` also forces a retrieval on the first data request after the backend starts. Cache use and retrieval timestamps are exposed by summary and data-quality endpoints. An unavailable API produces HTTP 503; no fabricated data is returned.

## Endpoints

`GET /api/health`, `/api/summary`, `/api/forecasts?start_date=2026-01-01&end_date=2026-01-31`, `/api/accuracy`, `/api/forecasts/vintages?delivery_date=2026-01-15`, `/api/data-quality`, and `/api/export/csv`; `POST /api/refresh` explicitly retrieves and caches source data. Summary, accuracy, and quality totals use the same selected date range as the period list.

Metrics are MAE, RMSE, and forecast minus actual bias. Missing values are not interpolated or treated as zero. The January completeness check is 744 hourly comparison periods; an hourly actual is missing if either of its two source half-hours is missing.

The official dataset documentation is at the Elexon BMRS API documentation pages for [FUELHH](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream) and [WINDFOR](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream). The public API requires no API key. FUELHH filters by settlement date and fuel type; WINDFOR filters by publication time. The API contract can change; verify historical availability at runtime.

AI tools assisted the initial implementation and documentation. Tests in this repository cover the core metric, selection, and timezone logic; live Elexon availability and response compatibility require an environment with network access.
