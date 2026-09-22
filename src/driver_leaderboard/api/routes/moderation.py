import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from driver_leaderboard.database import get_session
from driver_leaderboard.schemas.moderation import (
    ModerationDecisionCreate,
    ModerationDecisionResponse,
)
from driver_leaderboard.services.moderation_service import moderate_review
from driver_leaderboard.services.review_service import ReviewServiceError

router = APIRouter(prefix="/reviews", tags=["moderation"])


@router.post("/{review_id}/moderation-decisions", response_model=ModerationDecisionResponse)
def create_moderation_decision(
    review_id: uuid.UUID,
    payload: ModerationDecisionCreate,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
    moderator_id: Annotated[str, Header(alias="X-Moderator-ID", min_length=1, max_length=120)],
    session: Session = Depends(get_session),
) -> dict[str, object]:
    try:
        return moderate_review(
            session,
            review_id=review_id,
            moderator_id=moderator_id,
            action=payload.action,
            reason=payload.reason,
            idempotency_key=idempotency_key,
        ).body
    except ReviewServiceError as exc:
        session.rollback()
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
