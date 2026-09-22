# Iteration 017: Redis read comparison

- Read p95 improvement: 83.4%
- Throughput multiplier: 9.02x

```json
{
  "dataset": {
    "cities": 100,
    "drivers": 10000,
    "reviews": 500000
  },
  "read_p95_improvement_percent": 83.4,
  "read_throughput_multiplier": 9.02,
  "postgres": {
    "workers": 20,
    "leaderboard_reads": 5000,
    "leaderboard_reads_per_second": 940.2,
    "leaderboard_read_p50_ms": 14.466,
    "leaderboard_read_p95_ms": 28.338,
    "review_writes": 0,
    "review_writes_per_second": 0.0,
    "review_write_p50_ms": 0.0,
    "review_write_p95_ms": 0.0,
    "outbox_before_drain": {
      "pending_events": 0,
      "processing_events": 0,
      "completed_events": 10017,
      "failed_events": 0,
      "oldest_pending_age_seconds": null
    },
    "cache": {
      "enabled": false,
      "hits": 0,
      "misses": 0,
      "writes": 0,
      "errors": 0,
      "hit_rate": 0.0
    }
  },
  "redis": {
    "workers": 20,
    "leaderboard_reads": 5000,
    "leaderboard_reads_per_second": 8483.7,
    "leaderboard_read_p50_ms": 2.02,
    "leaderboard_read_p95_ms": 4.691,
    "review_writes": 0,
    "review_writes_per_second": 0.0,
    "review_write_p50_ms": 0.0,
    "review_write_p95_ms": 0.0,
    "outbox_before_drain": {
      "pending_events": 0,
      "processing_events": 0,
      "completed_events": 10017,
      "failed_events": 0,
      "oldest_pending_age_seconds": null
    },
    "cache": {
      "enabled": true,
      "hits": 5000,
      "misses": 0,
      "writes": 0,
      "errors": 0,
      "hit_rate": 1.0
    }
  }
}
```
