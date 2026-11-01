import json

from linuxops import cli
from linuxops.store import TelemetryStore


def test_snapshot_json(monkeypatch, capsys, sample):
    monkeypatch.setattr(cli, "_sample", lambda: sample)
    assert cli.main(["snapshot", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["context"] == "host"


def test_save_and_csv(tmp_path, monkeypatch, capsys, sample):
    local = TelemetryStore(tmp_path / "telemetry.db")
    monkeypatch.setattr(cli, "_db", lambda: local)
    monkeypatch.setattr(cli, "_sample", lambda: sample)
    assert cli.main(["snapshot", "--save"]) == 0
    capsys.readouterr()
    assert cli.main(["report", "--format", "csv"]) == 0
    output = capsys.readouterr().out
    assert "cpu_percent" in output
    assert "31.2" in output


def test_watch_count(monkeypatch, capsys, sample):
    saved = []
    monkeypatch.setattr(cli, "_sample", lambda: sample)
    monkeypatch.setattr(cli, "_db", lambda: type("DB", (), {"save": lambda self, s: saved.append(s)})())
    monkeypatch.setattr(cli.time, "sleep", lambda t: None)
    assert cli.main(["watch", "--interval", "5", "--count", "3"]) == 0
    assert len(saved) == 3
