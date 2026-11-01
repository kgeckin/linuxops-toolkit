from fastapi.testclient import TestClient

from linuxops.service import make_app
from linuxops.store import TelemetryStore


def client_for(tmp_path):
    return TestClient(make_app(store=TelemetryStore(tmp_path / "metrics.db"), collect_on_start=False))


def test_empty_api_state(tmp_path):
    with client_for(tmp_path) as client:
        assert client.get("/health").status_code == 200
        summary = client.get("/api/v1/overview").json()
        assert summary["ready"] is False
        assert summary["sample"] is None
        assert client.get("/metrics").text.startswith("# No LinuxOps sample")
        assert client.get("/api/v1/alerts").json() == {"status": "waiting", "alerts": []}


def test_saved_api_state(tmp_path, sample):
    app = make_app(store=TelemetryStore(tmp_path / "metrics.db"), collect_on_start=False)
    app.state.store.save(sample)
    with TestClient(app) as client:
        response = client.get("/api/v1/overview")
        assert response.status_code == 200
        assert response.json()["ready"] is True
        assert response.json()["sample"]["cpu"]["percent"] == 31.2
        assert client.get("/api/v1/history?minutes=60").json()["points"]
        assert "linuxops_cpu_utilization_percent" in client.get("/metrics").text
        assert "text/html" in client.get("/").headers["content-type"]
        assert ":root" in client.get("/static/styles.css").text


def test_history_validation(tmp_path):
    with client_for(tmp_path) as client:
        assert client.get("/api/v1/history?minutes=1").status_code == 422
        assert client.get("/api/v1/history?minutes=20000").status_code == 422
        assert client.post("/api/v1/overview").status_code == 405
