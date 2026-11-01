"""Tests for the shared, opt-in near-real-time read-only telemetry channel."""
from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from linuxops.service import configured_interval, make_app, network_rate, sse_event
from linuxops.store import TelemetryStore


def test_default_intervals(monkeypatch):
    monkeypatch.delenv("LINUXOPS_LIVE_INTERVAL", raising=False)
    monkeypatch.delenv("LINUXOPS_RECORD_INTERVAL", raising=False)
    assert configured_interval("LINUXOPS_LIVE_INTERVAL", 2, low=1, high=60) == 2
    assert configured_interval("LINUXOPS_RECORD_INTERVAL", 30, low=5, high=3600) == 30


@pytest.mark.parametrize("value", ["0", "61", "x", "-1"])
def test_invalid_live_intervals(monkeypatch, value):
    monkeypatch.setenv("LINUXOPS_LIVE_INTERVAL", value)
    with pytest.raises(ValueError):
        configured_interval("LINUXOPS_LIVE_INTERVAL", 2, low=1, high=60)


def test_valid_adjustable_live_interval(monkeypatch):
    monkeypatch.setenv("LINUXOPS_LIVE_INTERVAL", "1")
    assert configured_interval("LINUXOPS_LIVE_INTERVAL", 2, low=1, high=60) == 1


def test_network_rate_calculation(sample):
    previous = deepcopy(sample)
    current = deepcopy(sample)
    current["timestamp"] = (datetime.fromisoformat(sample["timestamp"]) + timedelta(seconds=2)).isoformat()
    current["network"]["bytes_received"] += 4096
    current["network"]["bytes_sent"] += 1000
    assert network_rate(previous, current) == {"rx_bytes_per_sec": 2048.0, "tx_bytes_per_sec": 500.0}


def test_network_rate_first_sample(sample):
    assert network_rate(None, sample) == {"rx_bytes_per_sec": None, "tx_bytes_per_sec": None}


def test_counter_reset_not_fake_traffic(sample):
    previous = deepcopy(sample)
    current = deepcopy(sample)
    current["timestamp"] = (datetime.fromisoformat(sample["timestamp"]) + timedelta(seconds=2)).isoformat()
    current["network"]["bytes_sent"] -= 1000
    assert network_rate(previous, current)["tx_bytes_per_sec"] is None


def test_instant_overview_uses_memory_even_when_not_archived(tmp_path, sample):
    store = TelemetryStore(tmp_path / "metrics.sqlite")
    app = make_app(store=store, collect_on_start=False)
    app.state.latest_sample = sample
    with TestClient(app) as client:
        result = client.get("/api/v1/overview").json()
        assert result["sample"] == sample
        assert result["health"]["status"] == "healthy"
        assert result["sample_count"] == 0
        assert client.get("/metrics").status_code == 200
        health = client.get("/health").json()
        assert health["live_interval_seconds"] == 2
        assert health["record_interval_seconds"] == 30


def test_live_route_exists_and_stream_replays_snapshot(tmp_path, sample):
    store = TelemetryStore(tmp_path / "metrics.sqlite")
    app = make_app(store=store, collect_on_start=False)
    app.state.latest_sample = sample
    route = next(r for r in app.routes if getattr(r, "path", None) == "/api/v1/live")

    async def inspect():
        response = await route.endpoint()
        assert isinstance(response, StreamingResponse)
        assert response.media_type == "text/event-stream"
        assert response.headers["cache-control"].startswith("no-store")
        assert len(app.state.subscribers) == 1
        iterator = response.body_iterator
        retry = await anext(iterator)
        event = await anext(iterator)
        assert retry.startswith("retry:")
        assert "event: reading\n" in event
        payload = json.loads(event.split("data: ")[1].strip())
        assert payload["sample"]["cpu"]["percent"] == 31.2
        await iterator.aclose()
        assert len(app.state.subscribers) == 0

    asyncio.run(inspect())


def test_live_route_waiting_and_bounded_queue(tmp_path):
    app = make_app(store=TelemetryStore(tmp_path / "metrics.sqlite"), collect_on_start=False)
    route = next(r for r in app.routes if getattr(r, "path", None) == "/api/v1/live")

    async def inspect():
        response = await route.endpoint()
        assert len(app.state.subscribers) == 1
        queue = next(iter(app.state.subscribers))
        assert queue.maxsize == 1
        iterator = response.body_iterator
        await anext(iterator)
        assert "event: status" in await anext(iterator)
        await iterator.aclose()
        assert not app.state.subscribers

    asyncio.run(inspect())


def test_sse_payload_safe_from_line_break_injection():
    event = sse_event("status", {"message": "line\nevent: forged"})
    assert event.count("\nevent:") == 0
    assert len(event.split("\ndata: ")) == 2
    assert json.loads(event.split("data: ")[1].strip()) == {"message": "line\nevent: forged"}
