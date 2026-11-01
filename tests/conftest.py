from datetime import datetime, timezone

import pytest


@pytest.fixture()
def sample():
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "context": "host",
        "os": "Linux",
        "cpu": {"percent": 31.2, "logical_cores": 8, "load_1m": 1.0,
                "load_5m": 0.8, "load_15m": 0.5},
        "memory": {"total_bytes": 16_000_000_000, "used_bytes": 8_000_000_000,
                   "percent": 50, "swap_total_bytes": 0, "swap_used_bytes": 0},
        "disk": {"mount": "/", "total_bytes": 1_000_000_000_000,
                 "used_bytes": 400_000_000_000, "free_bytes": 600_000_000_000,
                 "percent": 40},
        "network": {"bytes_sent": 1_000, "bytes_received": 2_000,
                    "packets_sent": 10, "packets_received": 20},
        "uptime_seconds": 4000,
    }
