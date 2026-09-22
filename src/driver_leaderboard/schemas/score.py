import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class DriverScoreResponse(BaseModel):
    city_id: uuid.UUID
    driver_id: uuid.UUID
    rating_sum: int
    contributing_review_count: int
    average_rating: Decimal | None
    eligible: bool
    window_start: datetime
    calculated_at: datetime
