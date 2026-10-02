import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.tenant import PlanTier


class TenantCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    name: str = Field(..., min_length=1, max_length=255)
    plan: PlanTier = PlanTier.STARTER

    model_config = ConfigDict(extra="forbid")

    @field_validator("slug")
    @classmethod
    def slug_no_leading_trailing_dash(cls, v: str) -> str:
        if v.startswith("-") or v.endswith("-"):
            raise ValueError("Slug must not start or end with a dash")
        return v


class TenantUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    plan: PlanTier | None = None
    settings: dict | None = None
    sso_provider: str | None = None

    model_config = ConfigDict(extra="forbid")


class TenantRead(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    plan: PlanTier
    sso_provider: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
