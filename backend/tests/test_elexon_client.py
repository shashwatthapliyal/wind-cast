from datetime import datetime, timezone

import pytest
import httpx

from app.services import elexon_client
from app.services.elexon_client import ElexonClient, ElexonClientError


class FakeResponse:
    status_code = 200
    headers = {}

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeAsyncClient:
    response = None
    calls = []

    def __init__(self, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, url, params):
        self.calls.append((url, params))
        return self.response


@pytest.mark.asyncio
async def test_fuelhh_uses_settlement_filters_and_array_response(monkeypatch):
    FakeAsyncClient.calls = []
    FakeAsyncClient.response = FakeResponse([{"fuelType": "WIND", "generation": 0}])
    monkeypatch.setattr(elexon_client.httpx, "AsyncClient", FakeAsyncClient)
    client = ElexonClient("https://data.elexon.co.uk/bmrs/api/v1", 2, 0)

    rows = await client.fetch_fuelhh(datetime(2026, 1, 1).date(), datetime(2026, 1, 2).date())

    assert rows == [{"fuelType": "WIND", "generation": 0}]
    url, params = FakeAsyncClient.calls[0]
    assert url.endswith("/datasets/FUELHH/stream")
    assert params == {
        "settlementDateFrom": "2026-01-01",
        "settlementDateTo": "2026-01-02",
        "fuelType": "WIND",
    }


@pytest.mark.asyncio
async def test_windfor_uses_publication_time_filters(monkeypatch):
    FakeAsyncClient.calls = []
    FakeAsyncClient.response = FakeResponse([])
    monkeypatch.setattr(elexon_client.httpx, "AsyncClient", FakeAsyncClient)
    client = ElexonClient("https://data.elexon.co.uk/bmrs/api/v1", 2, 0)

    assert await client.fetch_windfor(
        datetime(2025, 12, 31, tzinfo=timezone.utc),
        datetime(2026, 2, 1, tzinfo=timezone.utc),
    ) == []
    url, params = FakeAsyncClient.calls[0]
    assert url.endswith("/datasets/WINDFOR/stream")
    assert params == {
        "publishDateTimeFrom": "2025-12-31T00:00:00Z",
        "publishDateTimeTo": "2026-02-01T00:00:00Z",
    }


@pytest.mark.asyncio
async def test_stream_response_must_be_an_array(monkeypatch):
    FakeAsyncClient.response = FakeResponse({"data": []})
    monkeypatch.setattr(elexon_client.httpx, "AsyncClient", FakeAsyncClient)
    client = ElexonClient("https://data.elexon.co.uk/bmrs/api/v1", 2, 0)

    with pytest.raises(ElexonClientError, match="expected an array"):
        await client.fetch_fuelhh(datetime(2026, 1, 1).date(), datetime(2026, 1, 1).date())


@pytest.mark.asyncio
async def test_rate_limit_error_is_reported_without_retry_after_limit(monkeypatch):
    request = httpx.Request("GET", "https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream")
    response = httpx.Response(429, request=request, headers={"Retry-After": "0"})

    class RateLimitedClient(FakeAsyncClient):
        async def get(self, url, params):
            raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    monkeypatch.setattr(elexon_client.httpx, "AsyncClient", RateLimitedClient)
    client = ElexonClient("https://data.elexon.co.uk/bmrs/api/v1", 2, 0)

    with pytest.raises(ElexonClientError, match="rate limited.*HTTP 429"):
        await client.fetch_fuelhh(datetime(2026, 1, 1).date(), datetime(2026, 1, 1).date())


@pytest.mark.asyncio
async def test_network_error_is_distinguished(monkeypatch):
    class OfflineClient(FakeAsyncClient):
        async def get(self, url, params):
            raise httpx.ConnectError("DNS lookup failed")

    monkeypatch.setattr(elexon_client.httpx, "AsyncClient", OfflineClient)
    client = ElexonClient("https://data.elexon.co.uk/bmrs/api/v1", 2, 0)

    with pytest.raises(ElexonClientError, match="Could not connect to Elexon"):
        await client.fetch_fuelhh(datetime(2026, 1, 1).date(), datetime(2026, 1, 1).date())
