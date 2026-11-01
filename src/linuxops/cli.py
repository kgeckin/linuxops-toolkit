"""Human-friendly LinuxOps CLI with read-only defaults."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .collector import collect
from .rules import evaluate
from .store import TelemetryStore


def _db() -> TelemetryStore:
    return TelemetryStore(os.environ.get(
        "LINUXOPS_DB_PATH", str(Path.home() / ".local/share/linuxops/telemetry.db")))


def _sample() -> dict:
    disk = os.environ.get("LINUXOPS_DISK_PATH", "/")
    context = os.environ.get("LINUXOPS_CONTEXT", "host")
    return collect(disk, context=context)


def _display(sample: dict) -> None:
    def used_gb(n: int) -> str:
        return f"{n / 1_000_000_000:.1f} GB"
    print("\n LINUXOPS / SYSTEM SNAPSHOT")
    print(" " + "─" * 43)
    print(" Timestamp    " + sample["timestamp"])
    print(" Scope        " + sample["context"].upper())
    print(f" CPU          {sample['cpu']['percent']:.1f}% / {sample['cpu']['logical_cores']} cores")
    print(f" Memory       {sample['memory']['percent']:.1f}%  {used_gb(sample['memory']['used_bytes'])} / {used_gb(sample['memory']['total_bytes'])}")
    print(f" Disk         {sample['disk']['percent']:.1f}%  {used_gb(sample['disk']['used_bytes'])} / {used_gb(sample['disk']['total_bytes'])}")
    print(f" Network      ↑ {used_gb(sample['network']['bytes_sent'])}  ↓ {used_gb(sample['network']['bytes_received'])} (cumulative)")
    print(f" Uptime       {sample['uptime_seconds'] // 3600}h")
    for alarm in evaluate(sample):
        print(f" {alarm['severity'].upper()}      {alarm['message']}")
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="linuxops", description="Local-first Linux observability")
    parser.add_argument("--version", action="version", version=f"linuxops {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("snapshot", help="Read the current Linux OS counters")
    capture.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    capture.add_argument("--save", action="store_true", help="Persist the reading to SQLite")
    watch = commands.add_parser("watch", help="Observe repeatedly; stop with Ctrl+C")
    watch.add_argument("--interval", type=int, default=15, help="Seconds between readings (minimum 5)")
    watch.add_argument("--count", type=int, default=0, help="Stop after N readings; 0 means continuous")
    report = commands.add_parser("report", help="Export locally recorded history")
    report.add_argument("--format", choices=("json", "csv"), default="json")
    report.add_argument("--limit", type=int, default=120)
    serve = commands.add_parser("serve", help="Run a localhost-only dashboard and API")
    serve.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1", "localhost"))
    serve.add_argument("--port", type=int, default=8765)
    commands.add_parser("doctor", help="Check Linux environment and telemetry readiness")
    args = parser.parse_args(argv)
    try:
        if args.command == "snapshot":
            sample = _sample()
            if args.save:
                _db().save(sample)
            if args.json:
                print(json.dumps(sample, indent=2))
            else:
                _display(sample)
        elif args.command == "watch":
            if args.interval < 5 or args.count < 0:
                parser.error("Watch interval must be >=5 and count must be >=0")
            current = 0
            while not args.count or current < args.count:
                sample = _sample()
                _db().save(sample)
                _display(sample)
                current += 1
                if current != args.count:
                    time.sleep(args.interval)
        elif args.command == "report":
            points = _db().recent(limit=args.limit)
            if args.format == "json":
                print(json.dumps(points, indent=2))
            else:
                writer = csv.writer(sys.stdout)
                writer.writerow(("timestamp", "context", "cpu_percent", "memory_percent", "disk_percent", "network_bytes_sent", "network_bytes_received"))
                for p in points:
                    writer.writerow((p["timestamp"], p["context"], p["cpu"]["percent"], p["memory"]["percent"], p["disk"]["percent"], p["network"]["bytes_sent"], p["network"]["bytes_received"]))
        elif args.command == "doctor":
            s = _sample()
            print(f"LinuxOps {__version__}: telemetry available on {s['os']} ({s['context']})")
            print(f"Disk target: {s['disk']['mount']}")
            print("All values are read-only. No SSH or remote scan was performed.")
        elif args.command == "serve":
            import uvicorn
            from .service import make_app
            print(f"LinuxOps: http://127.0.0.1:{args.port}")
            print("WARNING: This dashboard has no login and must remain on loopback.")
            uvicorn.run(make_app(), host=args.host, port=args.port, log_level="info")
    except KeyboardInterrupt:
        print("\nLinuxOps stopped.", file=sys.stderr)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"LinuxOps error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
