import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from driver_leaderboard.database import get_session
from driver_leaderboard.schemas.leaderboard import LeaderboardResponse
from driver_leaderboard.services.cache_service import get_cached_or_authoritative_leaderboard
from driver_leaderboard.services.leaderboard_service import LeaderboardNotFound

router = APIRouter(prefix="/cities", tags=["leaderboards"])


@router.get("/{city_id}/leaderboard", response_model=LeaderboardResponse)
def read_leaderboard(
    city_id: uuid.UUID, session: Session = Depends(get_session)
) -> dict[str, object]:
    try:
        return get_cached_or_authoritative_leaderboard(session, city_id=city_id)
    except LeaderboardNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
