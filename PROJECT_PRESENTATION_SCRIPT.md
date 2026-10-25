# WindCast Project Presentation Script

## Purpose

This script is designed for a maximum 10-minute submission video:

- **Part 1: Client product demo** — up to 5 minutes
- **Part 2: Technical lead walkthrough** — up to 5 minutes

Replace bracketed items such as `[deployed URL]` with the final submission
details before recording. Do not claim a deployment or live URL unless it has
been tested from an external/incognito browser.

---

## Part 1 — Client presentation and product demo

**Target duration: 4 minutes 30 seconds**

### 0:00–0:30 — Business context

**On screen:** Open the application on the Overview page.

**Say:**

> WindCast is a decision-support product for a UK energy procurement team.
> The team must buy electricity in the day-ahead market, before the delivery
> day is complete. Wind generation is variable, so the procurement decision
> depends on the latest available wind forecast and an honest understanding of
> forecast error.
>
> This pilot focuses on national UK wind generation using Elexon BMRS data for
> January 2026. It brings the forecast decision and the forecast performance
> into one place.

### 0:30–1:20 — Overview and decision context

**On screen:** Point to the Overview header, date window, source status, KPI cards,
and chart.

**Say:**

> The Overview is the operational starting point. The selected delivery window
> is visible at the top, together with the Elexon BMRS source status.
>
> The KPI cards summarise mean absolute error, root mean square error, forecast
> bias, matched periods, and data coverage. These are calculated from the
> underlying matched actual and forecast records; they are not hardcoded demo
> numbers.
>
> The chart compares actual wind generation with the selected forecast over
> time. The solid teal line is actual generation, and the dashed blue line is
> the forecast. This makes periods of over- and under-forecasting visible
> immediately.

### 1:20–2:00 — Date filtering

**On screen:** Change the From or To date in the delivery window filter.

**Say:**

> The delivery window is interactive. When the dates change, the frontend
> requests the corresponding range from the backend and refreshes the summary,
> forecast records, accuracy metrics, and data-quality results together.
>
> This is important for procurement analysis because the user can move from a
> broad period to a specific delivery day without changing the analytical
> rules.

### 2:00–2:50 — Forecast analysis

**On screen:** Open **Forecast analysis**. Sort the table and show the forecast
vintage control.

**Say:**

> Forecast analysis provides the period-level evidence behind the summary.
> Each row shows the delivery period, the selected forecast, the observed
> generation, the error, and the forecast publication time where available.
>
> The table can be sorted to investigate the largest misses or inspect the
> delivery sequence. The vintage control allows the user to inspect the
> forecast publications available for a selected delivery date.
>
> The key decision rule is visible in the application: the selected forecast
> is the latest eligible publication at or before the configured decision
> cutoff. That makes the comparison representative of information available
> when the day-ahead decision would have been made.

### 2:50–3:35 — Accuracy and data quality

**On screen:** Open **Forecast accuracy**, then **Data quality**.

**Say:**

> Forecast accuracy converts the comparison into decision-ready metrics:
> MAE for the typical absolute miss, RMSE for greater sensitivity to large
> misses, bias for systematic over- or under-forecasting, and the largest
> individual miss.
>
> The daily breakdown helps the team see whether the overall result is driven
> by a particular day.
>
> Data quality is deliberately separate from forecast performance. It shows
> source health, cache status, observed and expected periods, missing actuals,
> missing forecasts, and the last retrieval time. Missing data is reported as
> missing; it is not silently converted to zero.

### 3:35–4:30 — Value and close

**On screen:** Return to Overview and point to the chart legend and KPI values.

**Say:**

> The value of WindCast is that it connects three questions a procurement user
> needs to answer:
>
> 1. What wind generation was forecast for the delivery window?
> 2. How accurate was that forecast historically?
> 3. Can I trust the completeness and freshness of the underlying data?
>
> The result is a focused pilot rather than a black-box recommendation engine.
> It gives the team transparent evidence for estimating the residual power
> requirement that may need to be procured from other sources.
>
> The scope is intentionally national wind generation from Elexon only. That
> creates a clear foundation for a later production phase, where other
> renewable sources, demand forecasts, prices, and portfolio-specific
> positions could be added without changing the core decision workflow.

---

## Part 2 — Technical lead walkthrough

**Target duration: 4 minutes 45 seconds**

### 5:00–5:35 — Architecture

**On screen:** Show the repository tree.

**Say:**

> The application is split into a React frontend and a Python FastAPI backend.
> The frontend is under `frontend/src`; the backend is under `backend/app`.
>
> React owns page state, date filters, navigation, tables, chart rendering,
> loading states, and user actions. FastAPI owns source retrieval, cache
> management, validation, record matching, forecast selection, analytics, and
> API responses.
>
> The backend includes a Dockerfile for containerised deployment. The frontend
> is a Vite production bundle that can be served by a static host such as
> Vercel, while the API can run as a container or hosted FastAPI service.

### 5:35–6:25 — Data pipeline and time resolution

**On screen:** Open `backend/app/services/matching.py`.

**Say:**

> Elexon FUELHH actuals arrive at 30-minute resolution, while WINDFOR
> forecasts are hourly. The backend first normalises timestamps to UTC and
> averages the two complete half-hour actual values into the corresponding
> hourly actual.
>
> If either half-hour observation is missing, the hourly actual remains
> unavailable. This avoids treating incomplete source data as a valid
> measurement.
>
> Actuals and forecast records are then matched by delivery timestamp. The
> resulting record keeps the actual value, selected forecast, publication time,
> signed error, and absolute error.

### 6:25–7:10 — Forecast selection and analytical integrity

**On screen:** Open the forecast-selection service and the backend README.

**Say:**

> Forecast selection is separated from matching so the business rule is
> explicit and testable. For each delivery timestamp, the service selects the
> latest forecast publication that satisfies the configured cutoff.
>
> The cutoff is an analytical assumption, currently configured as 24 hours
> before delivery by default. It is clearly described as an assumption rather
> than presented as an official market deadline.
>
> This distinction protects the integrity of the evaluation: the application
> does not choose a forecast with information that would not have been
> available for the intended procurement decision.

### 7:10–7:55 — API and frontend integration

**On screen:** Show `backend/app/main.py`, then the frontend `main.jsx`.

**Say:**

> The main API surfaces are health, summary, forecasts, accuracy, data quality,
> forecast vintages, CSV export, and an explicit refresh endpoint.
>
> The frontend requests the selected date range and keeps the visualisations
> tied to the same response contract. It uses `Promise.allSettled` rather than
> allowing one failed request to blank the whole interface. Successful
> responses can still populate the relevant sections, while failures are
> surfaced through a visible retry state.
>
> This is particularly important for a data application: an unavailable
> upstream API must produce a clear error or degraded state, never fabricated
> metrics.

### 7:55–8:40 — UI design and responsive behaviour

**On screen:** Show the Overview, analysis table, accuracy table, and quality cards
at desktop and narrow viewport sizes.

**Say:**

> The interface uses a shared dark navy design system with tokenised
> backgrounds, panels, borders, text, and accent colours. Teal identifies
> actual generation and positive indicators; blue identifies forecasts; amber
> highlights bias and warnings.
>
> Navigation is shared across pages and remains horizontal and sticky. The
> content layout adapts at smaller widths, tables retain access through
> controlled scrolling, and the chart uses a responsive SVG viewBox rather
> than fixed pixel dimensions.
>
> Loading, empty, unavailable-data, and retry states are explicit. This keeps
> the application useful during source outages and prevents an empty screen
> from being mistaken for valid zero data.

### 8:40–9:25 — Testing and engineering practices

**On screen:** Show the test folder and run the test/build commands if recording a
live terminal.

**Say:**

> The backend tests cover analytics, forecast selection, matching, API
> responses, Elexon client behaviour, and date validation. The frontend is
> validated with the Vite production build and browser smoke checks across
> navigation states and responsive widths.
>
> The project also validates zero-generation values, missing records, invalid
> date ranges, unavailable upstream data, cache behaviour, and forecast vintage
> ordering.
>
> The production checks used for this version are:
>
> ```text
> cd frontend
> npm run build
>
> cd backend
> .venv/Scripts/python.exe -m pytest -q
> ```

### 9:25–9:45 — Limitations and next steps

**On screen:** Show the README or a final Overview screen.

**Say:**

> This is a focused pilot. It covers January 2026 national wind actuals and
> forecasts from Elexon, not a full utility portfolio or a trading
> optimisation system.
>
> Production next steps would include authenticated deployment, monitoring,
> scheduled data refresh, a durable cache, portfolio-specific demand and
> position data, price integration, and formal governance around the forecast
> cutoff assumption.
>
> The current design keeps those extensions practical because source access,
> matching, forecast selection, and analytics are already separated.

### 9:45–10:00 — Close

**Say:**

> In summary, WindCast provides a transparent path from source data to
> procurement insight: retrieve the Elexon data, select the forecast available
> at the decision point, compare it with hourly wind generation, quantify the
> error, and expose data quality alongside the result.
>
> The repository README contains the setup instructions, architecture notes,
> Docker instructions, API details, and—after deployment—the final deployment
> link: `[deployed URL]`.

---

## Recording checklist

Before recording:

- Start the backend and frontend and confirm the API is reachable.
- Confirm the Overview shows live values rather than a loading state.
- Test one date-range change.
- Open all four navigation pages.
- Open Forecast analysis and show a forecast publication timestamp.
- Open Forecast accuracy and Data quality.
- Confirm the deployed URL works in an incognito browser.
- Replace `[deployed URL]` in the closing line.
- Keep the complete recording under 10 minutes.
