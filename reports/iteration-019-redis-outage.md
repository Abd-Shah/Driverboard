# Concurrent service benchmark

```json
{
  "workers": 20,
  "leaderboard_reads": 2000,
  "leaderboard_reads_per_second": 732.3,
  "leaderboard_read_p50_ms": 25.644,
  "leaderboard_read_p95_ms": 41.155,
  "review_writes": 0,
  "review_writes_per_second": 0.0,
  "review_write_p50_ms": 0.0,
  "review_write_p95_ms": 0.0,
  "outbox_before_drain": {
    "pending_events": 0,
    "processing_events": 0,
    "completed_events": 11017,
    "failed_events": 0,
    "oldest_pending_age_seconds": null
  },
  "cache": {
    "enabled": true,
    "hits": 0,
    "misses": 0,
    "writes": 0,
    "errors": 4000,
    "hit_rate": 0.0
  }
}
```
