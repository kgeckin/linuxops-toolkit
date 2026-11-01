"""Read-only host telemetry without process, user, address, or file inspection."""
from __future__ import annotations

import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil


def _percentage(used: int, total: int) -> float:
    return round(100 * used / total, 1) if total else 0.0


def collect(disk_path: str = "/", *, context: str = "host") -> dict:
    """Read high-level system metrics from the *current OS process environment*.

    Running this inside Docker measures a container-scoped environment where
    exposed values depend on cgroups and host/kernel configuration. Never
    describe container readings as independently verified host metrics.
    """
    if platform.system() != "Linux":
        raise RuntimeError("LinuxOps Toolkit supports Linux hosts only (Ubuntu WSL included).")
    if context not in {"host", "container"}:
        raise ValueError("Context must be 'host' or 'container'.")
    disk_path = str(Path(disk_path).resolve(strict=True))
    if not Path(disk_path).is_dir():
        raise ValueError("Disk target must be an existing directory.")

    cpu = psutil.cpu_percent(interval=0.12)
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage(disk_path)
    net = psutil.net_io_counters()
    if net is None:
        raise RuntimeError("Network counters are unavailable.")
    try:
        l1, l5, l15 = os.getloadavg()
    except OSError:
        l1 = l5 = l15 = 0.0
    ts = datetime.now(timezone.utc).isoformat()
    uptime = max(0, int(time.time() - psutil.boot_time()))

    return {
        "timestamp": ts,
        "context": context,
        "os": "Linux",
        "cpu": {
            "percent": round(cpu, 1),
            "logical_cores": psutil.cpu_count(logical=True) or 1,
            "load_1m": round(l1, 2),
            "load_5m": round(l5, 2),
            "load_15m": round(l15, 2),
        },
        "memory": {
            "total_bytes": mem.total,
            "used_bytes": mem.used,
            "percent": _percentage(mem.used, mem.total),
            "swap_total_bytes": swap.total,
            "swap_used_bytes": swap.used,
        },
        "disk": {
            "mount": disk_path,
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "percent": round(disk.percent, 1),
        },
        "network": {
            "bytes_sent": net.bytes_sent,
            "bytes_received": net.bytes_recv,
            "packets_sent": net.packets_sent,
            "packets_received": net.packets_recv,
        },
        "uptime_seconds": uptime,
    }
