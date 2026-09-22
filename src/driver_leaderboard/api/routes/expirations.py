from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from driver_leaderboard.database import get_session
from driver_leaderboard.schemas.expiration import ExpirationCreate, ExpirationResponse
from driver_leaderboard.services.expiration_service import (
    run_city_expiration,
    serialize_expiration,
)

router = APIRouter(prefix="/admin/expiration-runs", tags=["admin"])


@router.post("", response_model=ExpirationResponse, status_code=201)
def run_expiration(
    payload: ExpirationCreate, session: Session = Depends(get_session)
) -> dict[str, object]:
    result = run_city_expiration(
        session, city_id=payload.city_id, effective_at=payload.effective_at
    )
    return serialize_expiration(result)
