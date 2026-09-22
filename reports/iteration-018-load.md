# Iteration 018: mixed load and convergence

```json
{
  "parameters": {
    "reads": 20000,
    "writes": 1000,
    "clients": 20,
    "worker_batch_size": 100,
    "write_city_id": "044c6900-ba46-4e89-94bd-ee46a53b15d1"
  },
  "duration_seconds": 6.706,
  "combined_operations_per_second": 3131.4,
  "read_p50_ms": 2.376,
  "read_p95_ms": 6.357,
  "write_p50_ms": 25.957,
  "write_p95_ms": 113.647,
  "peak_pending_events": 751,
  "events_created_and_completed": 1000,
  "worker": {
    "events": 1000,
    "drivers": 958,
    "generations": 13,
    "batches": 13
  },
  "final_outbox": {
    "pending_events": 0,
    "processing_events": 0,
    "completed_events": 11017,
    "failed_events": 0,
    "oldest_pending_age_seconds": null
  },
  "cache": {
    "enabled": true,
    "hits": 19897,
    "misses": 103,
    "writes": 116,
    "errors": 0,
    "hit_rate": 0.9949
  }
}
```
