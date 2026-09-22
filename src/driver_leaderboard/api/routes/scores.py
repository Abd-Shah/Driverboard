import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from driver_leaderboard.database import get_session
from driver_leaderboard.schemas.score import DriverScoreResponse
from driver_leaderboard.services.scoring_service import (
    ScoreNotFound,
    get_driver_score,
    serialize_score,
)

router = APIRouter(prefix="/cities", tags=["scores"])


@router.get("/{city_id}/drivers/{driver_id}/score", response_model=DriverScoreResponse)
def read_driver_score(
    city_id: uuid.UUID, driver_id: uuid.UUID, session: Session = Depends(get_session)
) -> dict[str, object]:
    try:
        score = get_driver_score(session, city_id=city_id, driver_id=driver_id)
    except ScoreNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return serialize_score(score)
