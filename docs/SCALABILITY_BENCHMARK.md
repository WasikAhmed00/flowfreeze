# FlowFreeze Scalability Benchmark

**Run:** 2026-10-07 04:48 UTC
**Workload:** deterministic synthetic transfers/cash-outs across a 10,000-wallet identifier domain
**Runtime:** Python 3.12.3, Linux x86_64, 6 logical CPUs, SQLite WAL with `synchronous=NORMAL`; one commit per ingested event.

The benchmark calls the same incremental stream processor used by `POST /api/transactions`. It records cumulative wall time at the target transaction counts, sums the processor's measured time and its bounded indexed-neighborhood graph time, then measures 40 FastAPI `TestClient` POST requests against a database already containing 100,000 stream events.

| Stream events | Elapsed time | Throughput | Mean processing/event | Mean graph processing/event |
|---:|---:|---:|---:|---:|
| 1,000 | 0.2004 s | 4,990.35 tx/s | 0.1321 ms | 0.0893 ms |
| 10,000 | 2.0859 s | 4,794.04 tx/s | 0.1344 ms | 0.0904 ms |
| 50,000 | 10.7999 s | 4,629.66 tx/s | 0.1370 ms | 0.0929 ms |
| 100,000 | 21.8066 s | 4,585.77 tx/s | 0.1381 ms | 0.0939 ms |

### API response sample at 100K persisted events

| Requests | Mean | p50 | p95 | Maximum |
|---:|---:|---:|---:|---:|
| 40 | 4.568 ms | 4.455 ms | 5.087 ms | 7.433 ms |

The HTTP sample includes request validation, indexed graph context lookup, synthetic scoring, a SQLite write and JSON serialization. It is an in-process client measurement, not a network round trip.

### Interpretation and limits

- This run demonstrates 100K-event persistence and local incremental analysis across a 10K-wallet domain; it does **not** establish production capacity or a service-level objective.
- It is a single-process benchmark, not concurrent load, multi-worker contention, failover, or a production MFS/provider test.
- The graph response is intentionally bounded to recent wallet neighborhoods in a 10-minute window, with indexed lookups; it does not rebuild or traverse a 100K-edge graph per request.
- Risk, taint estimate, alerts and predictions in this stream adapter are illustrative synthetic heuristics, not a calibrated fraud model or the existing scenario replay's proportional-taint calculation.
- API latency percentiles are from 40 sequential FastAPI `TestClient` requests and should not be compared with externally observed network latency.
- Data is synthetic and no Upay or other MFS production system was contacted.

Reproduce from the repository root with:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python scripts/benchmark_scalability.py
```

Machine-readable output from this run is in [`scalability_benchmark.json`](scalability_benchmark.json).