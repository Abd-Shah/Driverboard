import argparse
import json
import time

from driver_leaderboard.database import SessionLocal
from driver_leaderboard.services.worker_service import (
    WorkerBatchError,
    drain_outbox,
    process_batch,
    record_batch_failure,
    serialize_batch,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Process transactional outbox events")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--drain", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args()
    if args.drain:
        print(json.dumps(serialize_batch(drain_outbox(SessionLocal, batch_size=args.batch_size))))
        return 0
    while True:
        try:
            with SessionLocal() as session:
                result = process_batch(session, limit=args.batch_size)
        except WorkerBatchError as exc:
            with SessionLocal() as failure_session:
                record_batch_failure(failure_session, event_ids=exc.event_ids, error=str(exc.cause))
            if not args.loop:
                raise
            result = None
        if result is not None and result.events_processed:
            print(json.dumps(serialize_batch(result)))
        if not args.loop:
            return 0
        if result is None or result.events_processed == 0:
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
