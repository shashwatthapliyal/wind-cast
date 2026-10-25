import asyncio
from datetime import date, datetime, timezone
from typing import Any

import httpx


class ElexonClientError(RuntimeError):
    pass


class ElexonClient:
    def __init__(self, base_url: str, timeout: float, retries: int):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = max(0, retries)

    async def fetch_fuelhh(self, start: date, end: date, fuel_type: str = "WIND") -> list[dict[str, Any]]:
        return await self._fetch(
            "FUELHH",
            {
                "settlementDateFrom": start.isoformat(),
                "settlementDateTo": end.isoformat(),
                "fuelType": fuel_type,
            },
        )

    async def fetch_windfor(self, publish_from: datetime, publish_to: datetime) -> list[dict[str, Any]]:
        return await self._fetch(
            "WINDFOR",
            {
                "publishDateTimeFrom": self._iso_utc(publish_from),
                "publishDateTimeTo": self._iso_utc(publish_to),
            },
        )

    @staticmethod
    def _iso_utc(value: datetime) -> str:
        if value.tzinfo is None:
            raise ValueError("publication filters must include a timezone")
        return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    async def _fetch(self, dataset: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        for attempt in range(self.retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout, headers={"Accept": "application/json"}) as client:
                    response = await client.get(f"{self.base_url}/datasets/{dataset}/stream", params=params)
                response.raise_for_status()
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise ElexonClientError(f"Elexon {dataset} returned invalid JSON") from exc
                if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
                    raise ElexonClientError(f"Elexon {dataset} returned an unexpected response; expected an array of records")
                return payload
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                retryable = status == 429 or status >= 500
                if not retryable or attempt == self.retries:
                    if status == 400:
                        reason = "rejected the request parameters"
                    elif status in (401, 403):
                        reason = "denied access (authentication or quota issue)"
                    elif status == 429:
                        reason = "rate limited the request"
                    else:
                        reason = "returned an upstream server error"
                    raise ElexonClientError(f"Elexon {dataset} {reason} (HTTP {status})") from exc
                await asyncio.sleep(self._retry_delay(exc.response, attempt))
            except httpx.TimeoutException as exc:
                if attempt == self.retries:
                    raise ElexonClientError(f"Elexon {dataset} request timed out") from exc
                await asyncio.sleep(2 ** attempt)
            except httpx.TransportError as exc:
                if attempt == self.retries:
                    raise ElexonClientError(f"Could not connect to Elexon for {dataset}") from exc
                await asyncio.sleep(2 ** attempt)
            except ElexonClientError:
                raise
        raise ElexonClientError(f"Elexon {dataset} request failed")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(max(float(retry_after), 0), 30)
            except ValueError:
                try:
                    retry_at = datetime.strptime(retry_after, "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=timezone.utc)
                    return min(max((retry_at - datetime.now(timezone.utc)).total_seconds(), 0), 30)
                except ValueError:
                    pass
        return float(2 ** attempt)
