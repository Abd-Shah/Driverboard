import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class RebuildCreate(BaseModel):
    city_id: uuid.UUID


class RebuildResponse(BaseModel):
    id: uuid.UUID
    city_id: uuid.UUID
    status: str
    calculated_at: datetime
    base_generation_id: uuid.UUID
    candidate_generation_id: uuid.UUID | None
    comparison_summary: dict[str, Any] | None
    created_at: datetime
    completed_at: datetime | None
