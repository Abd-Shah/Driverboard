import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session

from driver_leaderboard.database import get_session
from driver_leaderboard.schemas.review import ReviewDeleteResponse, ReviewResponse, ReviewUpsert
from driver_leaderboard.services.review_service import (
    ReviewServiceError,
    delete_review,
    get_current_review,
    upsert_review,
)

router = APIRouter(prefix="/trips", tags=["reviews"])


@router.put("/{trip_id}/review", response_model=ReviewResponse)
def put_review(
    trip_id: uuid.UUID,
    payload: ReviewUpsert,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
    rider_id: Annotated[uuid.UUID, Header(alias="X-Rider-ID")],
    session: Session = Depends(get_session),
) -> dict[str, object]:
    try:
        result = upsert_review(
            session,
            trip_id=trip_id,
            rider_id=rider_id,
            rating=payload.rating,
            idempotency_key=idempotency_key,
        )
    except ReviewServiceError as exc:
        session.rollback()
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    response.status_code = 201 if result.created and not result.replayed else 200
    return result.body


@router.get("/{trip_id}/review", response_model=ReviewResponse)
def read_review(trip_id: uuid.UUID, session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        return get_current_review(session, trip_id=trip_id)
    except ReviewServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.delete("/{trip_id}/review", response_model=ReviewDeleteResponse)
def remove_review(
    trip_id: uuid.UUID,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
    rider_id: Annotated[uuid.UUID, Header(alias="X-Rider-ID")],
    session: Session = Depends(get_session),
) -> dict[str, object]:
    try:
        return delete_review(
            session,
            trip_id=trip_id,
            rider_id=rider_id,
            idempotency_key=idempotency_key,
        ).body
    except ReviewServiceError as exc:
        session.rollback()
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
