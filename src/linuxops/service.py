"""Local-only near-real-time sampling, SSE fanout and low-frequency SQLite archive.

One producer samples regardless of subscriber count. Each subscriber receives only
its newest queued reading, preventing a slow browser from growing server memory.
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from importlib.resources import files
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .collector import collect
from .rules import assessment
from .store import TelemetryStore


def configured_interval(name: str, default: int, *, low: int, high: int) -> int:
    """Reject unreasonably fast or slow sampler settings."""
    raw = os.environ.get(name, str(default))
    try:
        seconds = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer number of seconds") from exc
    if not low <= seconds <= high:
        raise ValueError(f"{name} must be between {low} and {high} seconds")
    return seconds


def network_rate(previous: dict | None, sample: dict) -> dict[str, float | None]:
    """Compute observed byte rate using two independent cumulative counter readings."""
    result: dict[str, float | None] = {"rx_bytes_per_sec": None, "tx_bytes_per_sec": None}
    if previous is None:
        return result
    elapsed = (datetime.fromisoformat(sample["timestamp"]) -
               datetime.fromisoformat(previous["timestamp"])).total_seconds()
    if elapsed <= 0:
        return result
    for metric, key in (("rx_bytes_per_sec", "bytes_received"),
                        ("tx_bytes_per_sec", "bytes_sent")):
        delta = sample["network"][key] - previous["network"][key]
        # Negative means counters reset, not negative traffic.
        result[metric] = round(delta / elapsed, 1) if delta >= 0 else None
    return result


def sse_event(event: str, payload: dict[str, Any]) -> str:
    """Safe SSE encoding: JSON eliminates CR/LF injection from the input data."""
    return f"event: {event}\ndata: {json.dumps(payload, separators=(',', ':'), ensure_ascii=True)}\n\n"


def make_app(*, store: TelemetryStore | None = None, collect_on_start: bool = True) -> FastAPI:
    source = store if store is not None else TelemetryStore(os.environ.get(
        "LINUXOPS_DB_PATH", os.path.expanduser("~/.local/share/linuxops/telemetry.db")))
    context = os.environ.get("LINUXOPS_CONTEXT", "host")
    live_interval = configured_interval("LINUXOPS_LIVE_INTERVAL", 2, low=1, high=60)
    record_interval = configured_interval("LINUXOPS_RECORD_INTERVAL", 30, low=5, high=3600)
    disk_path = os.environ.get("LINUXOPS_DISK_PATH", "/")
    root = files("linuxops").joinpath("web")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if not collect_on_start:
            yield
            return

        async def poll():
            last_save_time = float("-inf")
            previous: dict | None = None
            loop = asyncio.get_running_loop()
            while True:
                tick_start = loop.time()
                try:
                    sample = await asyncio.to_thread(collect, disk_path, context=context)
                    sample["network"].update(network_rate(previous, sample))
                    previous = sample
                    app.state.latest_sample = sample
                    app.state.last_error = None
                    should_save = tick_start - last_save_time >= record_interval
                    if should_save:
                        try:
                            await asyncio.to_thread(source.save, sample)
                            last_save_time = tick_start
                        except (OSError, ValueError, sqlite3.Error) as exc:
                            # Live monitoring remains available even if the archive fails.
                            app.state.last_error = f"{type(exc).__name__}: local history unavailable"
                    payload = {"sample": sample, "health": assessment(sample),
                               "recorded": should_save and app.state.last_error is None}
                    for queue in tuple(app.state.subscribers):
                        if queue.full():
                            try:
                                queue.get_nowait()
                            except asyncio.QueueEmpty:
                                pass
                        queue.put_nowait(payload)
                except (OSError, RuntimeError, ValueError) as exc:
                    app.state.last_error = f"{type(exc).__name__}: telemetry sample unavailable"
                # Account for the collector's nonzero measurement time.
                await asyncio.sleep(max(0.1, live_interval - (loop.time() - tick_start)))

        task = asyncio.create_task(poll(), name="linuxops-single-sampler")
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    app = FastAPI(
        title="LinuxOps Toolkit", version=__version__, lifespan=lifespan,
        description="Loopback Linux observability with live SSE and periodic SQLite history.",
    )
    app.state.store = source
    app.state.latest_sample = None
    app.state.subscribers = set()
    app.state.last_error = None

    def current() -> dict | None:
        return app.state.latest_sample or source.latest()

    @app.get("/health", tags=["system"])
    def health():
        sample = current()
        return {"status": "ok", "context": context, "version": __version__,
                "sample_count": source.count(), "last_error": app.state.last_error,
                "last_sample": sample["timestamp"] if sample else None,
                "live_interval_seconds": live_interval,
                "record_interval_seconds": record_interval}

    @app.get("/api/v1/overview", tags=["observability"])
    def overview():
        sample = current()
        if not sample:
            return {"ready": False, "context": context, "sample": None,
                    "health": None, "sample_count": source.count()}
        return {"ready": True, "context": context, "sample": sample,
                "health": assessment(sample), "sample_count": source.count()}

    @app.get("/api/v1/history", tags=["observability"])
    def history(minutes: int = Query(60, ge=5, le=10080),
                limit: int = Query(500, ge=1, le=5000)):
        start = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        return {"minutes": minutes, "points": source.recent(limit=limit, since=start)}

    @app.get("/api/v1/alerts", tags=["observability"])
    def alerts():
        sample = current()
        if not sample:
            return {"status": "waiting", "alerts": []}
        report = assessment(sample)
        return {"status": report["status"], "alerts": report["alerts"]}

    @app.get("/api/v1/live", tags=["observability"])
    async def live():
        """SSE stream of near-real-time local measurements, shared across clients."""
        if len(app.state.subscribers) >= 16:
            raise HTTPException(status_code=503, detail="Local viewer limit reached")
        queue: asyncio.Queue = asyncio.Queue(maxsize=1)
        app.state.subscribers.add(queue)

        async def events():
            try:
                yield "retry: 2500\n\n"
                sample = current()
                if sample:
                    yield sse_event("reading", {"sample": sample, "health": assessment(sample),
                                                "recorded": False})
                else:
                    yield sse_event("status", {"message": "Awaiting first reading"})
                while True:
                    try:
                        message = await asyncio.wait_for(queue.get(), timeout=15)
                        yield sse_event("reading", message)
                    except asyncio.TimeoutError:
                        yield ": heartbeat\n\n"
            finally:
                app.state.subscribers.discard(queue)

        return StreamingResponse(events(), media_type="text/event-stream", headers={
            "Cache-Control": "no-store, no-transform", "X-Accel-Buffering": "no",
            "X-Content-Type-Options": "nosniff",
        })

    @app.get("/metrics", response_class=PlainTextResponse, tags=["observability"])
    def prometheus():
        sample = current()
        if sample is None:
            return "# No LinuxOps sample yet\n"
        fields = [("cpu_utilization_percent", sample["cpu"]["percent"]),
                  ("memory_utilization_percent", sample["memory"]["percent"]),
                  ("disk_utilization_percent", sample["disk"]["percent"]),
                  ("memory_used_bytes", sample["memory"]["used_bytes"]),
                  ("network_bytes_received_total", sample["network"]["bytes_received"]),
                  ("network_bytes_sent_total", sample["network"]["bytes_sent"])]
        return "".join(f"# TYPE linuxops_{name} gauge\nlinuxops_{name} {value}\n" for name, value in fields)

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(str(root.joinpath("index.html")), headers={"Cache-Control": "no-cache"})

    app.mount("/static", StaticFiles(directory=str(root), html=False), name="static")
    return app


app = make_app()
