# LinuxOps Toolkit V2 Architecture

## The key separation: live vs. historical

```text
                  User runs: linuxops serve
                            |
           FastAPI server on 127.0.0.1:8765
                            |
             ONE shared psutil collector
                (every 2 seconds)
                            |
           +----------------+----------------+
           |                                 |
       LIVE MEMORY                       PERIODIC ARCHIVE
       latest sample                     SQLite every 30 s
       no database queries               local 7d retention
           |                                 |
       SSE /api/v1/live                 GET /api/v1/history
       event: reading                    (only when needed)
           |                                 |
           +----------------+----------------+
                            |
                    Browser dashboard
                  [Live] or [History]
```

The collector reads the chosen Linux environment from a single async task. One OS measurement is shared across all local tabs and dashboard viewers. Opening extra dashboards never starts extra collectors. The collector runs in a worker thread so CPU sampling does not block FastAPI's event loop.

## Update behavior

* **Live sampling:** every 2 seconds by default, configurable with `LINUXOPS_LIVE_INTERVAL` (1 to 60 seconds).
* **Transport:** Server-Sent Events (SSE) over `GET /api/v1/live`. Connected browsers get pushed measurements without constantly polling the API. EventSource automatically reconnects when a connection drops.
* **Network throughput:** rate computed from the delta of successive cumulative Linux network counters divided by measured elapsed seconds. A reset or first sample yields an unavailable rate, not an invented negative transfer speed.
* **Archiving:** only every 30 seconds by default, configurable with `LINUXOPS_RECORD_INTERVAL` (5 to 3600 seconds). The first sample is written immediately. Seven-day pruning happens on every archive save.
* **Live UI:** retains the most recent 120 readings in browser memory. In the default 2-second mode this covers approximately 4 minutes. This is not the SQLite history.
* **History UI:** queries archived readings only on switching to History, changing the time window and periodically while the History panel is open. Historical graph values do not pretend to be second-resolution data.
* **Resources:** each SSE subscription has a queue of size 1, replacing outdated messages for slow clients. SSE supports up to 16 local viewers. Hidden/paused browsers stop their stream. The local sampler continues for other viewers and archived history.
* **Freshness:** the UI shows the sample timestamp to the second and switches to reconnecting/stale states when new samples stop arriving.

## API

| Route | Method | Purpose |
| --- | --- | --- |
| `/health` | GET | Current service settings, sample freshness and saved count |
| `/api/v1/live` | GET, SSE | Pushes initial snapshot, then live readings |
| `/api/v1/overview` | GET | Latest in-memory snapshot and threshold status |
| `/api/v1/history` | GET | Archived SQLite samples, with time-window and count limits |
| `/api/v1/alerts` | GET | Threshold evaluation on the most recent snapshot |
| `/metrics` | GET | Current gauge values in Prometheus exposition format |
| `/docs` | GET | OpenAPI documentation |

No process access, remote commands, network scanning, SSH control, user identity collection or IP inventory is implemented. Data provenance remains explicit: native Ubuntu WSL reports the Linux environment, not Windows host utilization.

## Operational tradeoffs

* CPU percentage is sampled over a brief 120-millisecond psutil interval. A two-second sampling interval is **near real time**, not a physically continuous measurement or a hard latency guarantee.
* A connection may be delayed by machine load or OS scheduling.
* Reducing the live interval to one second can raise sample overhead and visual refresh activity.
* Large history windows and very high persistence rates increase storage and chart work. Archive interval should be chosen independently from live sampling.
* The server is loopback only and has no login. Do not expose it on any untrusted network.
