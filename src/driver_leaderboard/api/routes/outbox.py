from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from driver_leaderboard.database import get_session
from driver_leaderboard.services.worker_service import outbox_metrics

router = APIRouter(prefix="/admin/outbox", tags=["admin"])


@router.get("/metrics")
def read_outbox_metrics(session: Session = Depends(get_session)) -> dict[str, float | int | None]:
    return outbox_metrics(session)
