import json
from datetime import datetime, timedelta, timezone

import pytest

from linuxops.store import TelemetryStore


def test_history_and_latest_are_ordered(tmp_path, sample):
    store = TelemetryStore(tmp_path / "local.db")
    for i in (12, 29, 48):
        store.save({**sample, "cpu": {**sample["cpu"], "percent": i}})
    assert store.count() == 3
    assert [p["cpu"]["percent"] for p in store.recent()] == [12, 29, 48]
    assert store.latest()["cpu"]["percent"] == 48
    reopened = TelemetryStore(tmp_path / "local.db")
    assert reopened.count() == 3


def test_retention_prunes_expired_samples(tmp_path, sample):
    store = TelemetryStore(tmp_path / "local.db")
    # Backdate the payload beyond retention then save a current sample.
    older = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    store.save({**sample, "timestamp": older})
    store.save(sample)
    assert store.count() == 1
    assert store.latest()["timestamp"] == sample["timestamp"]


def test_validate_bounds_and_timestamps(tmp_path, sample):
    store = TelemetryStore(tmp_path / "local.db")
    with pytest.raises(ValueError):
        store.recent(limit=0)
    with pytest.raises(ValueError):
        store.recent(limit=5001)
    with pytest.raises(ValueError):
        store.save({**sample, "timestamp": "2026-01-01T00:00:00"})
    with pytest.raises(ValueError):
        TelemetryStore(tmp_path / "bad.db", retention_days=0)
