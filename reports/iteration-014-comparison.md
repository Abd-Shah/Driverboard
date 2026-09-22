# Iteration 014: asynchronous write comparison

- Write p95 improvement: 73.4%
- Write throughput improvement: 272.4%

```json
{
  "review_write_p95_improvement_percent": 73.4,
  "review_write_throughput_improvement_percent": 272.4,
  "phase2": {
    "workers": 10,
    "leaderboard_reads": 1000,
    "leaderboard_reads_per_second": 1077.7,
    "leaderboard_read_p50_ms": 7.64,
    "leaderboard_read_p95_ms": 18.328,
    "review_writes": 50,
    "review_writes_per_second": 131.6,
    "review_write_p50_ms": 69.055,
    "review_write_p95_ms": 110.603
  },
  "phase3": {
    "workers": 10,
    "leaderboard_reads": 1000,
    "leaderboard_reads_per_second": 1441.6,
    "leaderboard_read_p50_ms": 6.516,
    "leaderboard_read_p95_ms": 9.578,
    "review_writes": 50,
    "review_writes_per_second": 490.1,
    "review_write_p50_ms": 18.181,
    "review_write_p95_ms": 29.474,
    "outbox_before_drain": {
      "pending_events": 49,
      "processing_events": 0,
      "completed_events": 517,
      "failed_events": 0,
      "oldest_pending_age_seconds": 0.101
    },
    "worker": {
      "events_processed": 49,
      "drivers_recalculated": 49,
      "generations_published": 10,
      "convergence_duration_ms": 157.998,
      "outbox_after_drain": {
        "pending_events": 0,
        "processing_events": 0,
        "completed_events": 566,
        "failed_events": 0,
        "oldest_pending_age_seconds": null
      }
    }
  }
}
```
