import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from driver_leaderboard.database import get_session
from driver_leaderboard.schemas.rebuild import RebuildCreate, RebuildResponse
from driver_leaderboard.services.rebuild_service import (
    RebuildError,
    discard_rebuild,
    get_rebuild,
    publish_rebuild,
    serialize_rebuild,
    start_rebuild,
)

router = APIRouter(prefix="/admin/rebuilds", tags=["admin"])


def _handle(operation):
    try:
        return operation()
    except RebuildError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("", response_model=RebuildResponse, status_code=201)
def create_rebuild(
    payload: RebuildCreate, session: Session = Depends(get_session)
) -> dict[str, object]:
    job = _handle(lambda: start_rebuild(session, city_id=payload.city_id))
    return serialize_rebuild(job)


@router.get("/{rebuild_id}", response_model=RebuildResponse)
def read_rebuild(
    rebuild_id: uuid.UUID, session: Session = Depends(get_session)
) -> dict[str, object]:
    job = _handle(lambda: get_rebuild(session, rebuild_id=rebuild_id))
    return serialize_rebuild(job)


@router.post("/{rebuild_id}/publish", response_model=RebuildResponse)
def publish(rebuild_id: uuid.UUID, session: Session = Depends(get_session)) -> dict[str, object]:
    job = _handle(lambda: publish_rebuild(session, rebuild_id=rebuild_id))
    return serialize_rebuild(job)


@router.post("/{rebuild_id}/discard", response_model=RebuildResponse)
def discard(rebuild_id: uuid.UUID, session: Session = Depends(get_session)) -> dict[str, object]:
    job = _handle(lambda: discard_rebuild(session, rebuild_id=rebuild_id))
    return serialize_rebuild(job)
