"""Transparent, deterministic health thresholds; no predictive claims."""
from __future__ import annotations

from datetime import datetime, timezone

DEFAULT_LIMITS = {"cpu": 85.0, "memory": 85.0, "disk": 90.0}


def evaluate(sample: dict, limits: dict[str, float] | None = None) -> list[dict]:
    thresholds = DEFAULT_LIMITS if limits is None else limits
    alerts: list[dict] = []
    for name in ("cpu", "memory", "disk"):
        value = float(sample[name]["percent"])
        threshold = float(thresholds[name])
        if value >= threshold:
            alerts.append({
                "id": f"{name}-utilization",
                "severity": "critical" if value >= 95.0 else "warning",
                "metric": name,
                "value": value,
                "threshold": threshold,
                "message": f"{name.upper()} utilization {value:.1f}% exceeded {threshold:.0f}% threshold",
                "timestamp": sample["timestamp"],
            })
    return alerts


def assessment(sample: dict, *, stale_after: int = 90) -> dict:
    timestamp = datetime.fromisoformat(sample["timestamp"])
    if timestamp.tzinfo is None:
        raise ValueError("Samples must carry timezone-aware timestamps")
    age = (datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc)).total_seconds()
    issues = evaluate(sample)
    return {
        "status": "stale" if age > stale_after else ("attention" if issues else "healthy"),
        "age_seconds": max(0, int(age)),
        "alerts": issues,
    }
