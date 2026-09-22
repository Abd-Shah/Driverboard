import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class LeaderboardEntryResponse(BaseModel):
    rank: int
    driver_id: uuid.UUID
    stable_driver_id: str
    average_rating: Decimal
    contributing_review_count: int


class LeaderboardResponse(BaseModel):
    city_id: uuid.UUID
    generation_id: uuid.UUID
    version: int
    generated_at: datetime
    published_at: datetime
    source_scores_calculated_at: datetime | None
    entry_count: int
    entries: list[LeaderboardEntryResponse]
