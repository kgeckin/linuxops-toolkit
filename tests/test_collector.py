from types import SimpleNamespace

import pytest

from linuxops import collector


def test_percentage_has_safe_zero_denominator():
    assert collector._percentage(100, 0) == 0.0
    assert collector._percentage(1, 4) == 25.0


def test_collector_does_not_collect_sensitive_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(collector.platform, "system", lambda: "Linux")
    monkeypatch.setattr(collector.psutil, "cpu_percent", lambda interval: 13.1)
    monkeypatch.setattr(collector.psutil, "cpu_count", lambda logical: 4)
    monkeypatch.setattr(collector.psutil, "virtual_memory", lambda: SimpleNamespace(total=1000, used=340))
    monkeypatch.setattr(collector.psutil, "swap_memory", lambda: SimpleNamespace(total=200, used=20))
    monkeypatch.setattr(collector.psutil, "disk_usage", lambda _: SimpleNamespace(total=500, used=300, free=200, percent=60))
    monkeypatch.setattr(collector.psutil, "net_io_counters", lambda: SimpleNamespace(bytes_sent=12, bytes_recv=42, packets_sent=2, packets_recv=4))
    monkeypatch.setattr(collector.psutil, "boot_time", lambda: 100)
    monkeypatch.setattr(collector.os, "getloadavg", lambda: (1.1, 1.2, 1.3))
    snapshot = collector.collect(str(tmp_path))
    assert snapshot["cpu"]["percent"] == 13.1
    assert snapshot["memory"]["percent"] == 34
    assert snapshot["network"]["bytes_received"] == 42
    assert snapshot["disk"]["percent"] == 60
    assert not any(field in snapshot for field in ("users", "processes", "addresses", "credentials", "secrets"))


def test_non_linux_refused(monkeypatch):
    monkeypatch.setattr(collector.platform, "system", lambda: "Windows")
    with pytest.raises(RuntimeError):
        collector.collect()


def test_container_context_labeled(monkeypatch, tmp_path):
    monkeypatch.setattr(collector, "collect", lambda disk_path="/", context="host": {"context": context})
    assert collector.collect(str(tmp_path), context="container")["context"] == "container"
