import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ReviewUpsert(BaseModel):
    rating: int = Field(ge=1, le=5)


class ReviewResponse(BaseModel):
    review_id: uuid.UUID
    trip_id: uuid.UUID
    current_version: int
    rating: int
    created_at: datetime
    idempotent_replay: bool = False


class ReviewDeleteResponse(BaseModel):
    review_id: uuid.UUID
    trip_id: uuid.UUID
    deleted: bool
    changed_state: bool
    idempotent_replay: bool = False
