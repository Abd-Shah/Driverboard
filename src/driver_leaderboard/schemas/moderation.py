import uuid

from pydantic import BaseModel, Field


class ModerationDecisionCreate(BaseModel):
    action: str = Field(pattern="^(exclude|restore)$")
    reason: str | None = Field(default=None, max_length=500)


class ModerationDecisionResponse(BaseModel):
    decision_id: uuid.UUID
    review_id: uuid.UUID
    decision_number: int
    action: str
    excluded: bool
    changed_state: bool
    idempotent_replay: bool = False
