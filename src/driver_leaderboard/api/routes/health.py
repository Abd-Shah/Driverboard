from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from driver_leaderboard.database import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
def health(session: Session = Depends(get_session)) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}
