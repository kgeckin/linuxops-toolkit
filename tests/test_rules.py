from datetime import datetime, timedelta, timezone

from linuxops.rules import assessment, evaluate


def test_no_alerts_under_threshold(sample):
    assert evaluate(sample) == []
    assert assessment(sample)["status"] == "healthy"


def test_warning_and_critical(sample):
    modified = {**sample, "cpu": {**sample["cpu"], "percent": 86},
                "disk": {**sample["disk"], "percent": 97}}
    alerts = evaluate(modified)
    assert len(alerts) == 2
    assert {a["severity"] for a in alerts} == {"warning", "critical"}
    assert assessment(modified)["status"] == "attention"


def test_stale_status_takes_precedence(sample):
    old = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    assert assessment({**sample, "timestamp": old})["status"] == "stale"
