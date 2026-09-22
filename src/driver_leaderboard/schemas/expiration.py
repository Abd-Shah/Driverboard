import uuid
from datetime import datetime

from pydantic import BaseModel


class ExpirationCreate(BaseModel):
    city_id: uuid.UUID
    effective_at: datetime | None = None


class ExpirationResponse(BaseModel):
    id: uuid.UUID
    city_id: uuid.UUID
    effective_at: datetime
    status: str
    affected_drivers: int
    published_generation_id: uuid.UUID | None
    created_at: datetime
    completed_at: datetime | None
