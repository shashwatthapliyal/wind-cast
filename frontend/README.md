# Wind Forecast Intelligence

## Local development

1. In one terminal, follow `backend/README.md` to start FastAPI on `http://127.0.0.1:8000`.
2. In a second terminal, run these commands from `frontend`:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
npm ci
npm run dev
```

The frontend uses `http://127.0.0.1:8000` by default. Set `VITE_API_BASE_URL` in `frontend/.env` if the backend runs elsewhere. The production bundle is built with `npm run build` and can be served by Vercel or any static host. Set the backend's `WIND_CORS_ORIGINS` to include the deployed frontend origin.
