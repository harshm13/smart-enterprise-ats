import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.job import EmploymentType, ReqStatus
from app.schemas.common import PaginatedResponse


class RequirementItem(BaseModel):
    skill: str
    required: bool = True
    weight: float = Field(default=1.0, ge=0.0, le=1.0)


class JobCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    department: str | None = Field(None, max_length=100)
    location: str | None = Field(None, max_length=255)
    employment_type: EmploymentType | None = None
    description_raw: str = Field(..., min_length=50)
    requirements: list[RequirementItem] = Field(default_factory=list)
    salary_min: int | None = Field(None, ge=0)
    salary_max: int | None = Field(None, ge=0)
    currency: str = Field("USD", min_length=3, max_length=3)
    pipeline_template_id: uuid.UUID

    model_config = ConfigDict(extra="forbid")


class JobUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    department: str | None = None
    location: str | None = None
    employment_type: EmploymentType | None = None
    description_raw: str | None = Field(None, min_length=50)
    requirements: list[RequirementItem] | None = None
    salary_min: int | None = Field(None, ge=0)
    salary_max: int | None = Field(None, ge=0)
    currency: str | None = Field(None, min_length=3, max_length=3)

    model_config = ConfigDict(extra="forbid")


class JobRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_by_id: uuid.UUID
    pipeline_template_id: uuid.UUID
    title: str
    department: str | None
    location: str | None
    employment_type: EmploymentType | None
    description_raw: str
    requirements: list[Any]
    salary_min: int | None
    salary_max: int | None
    currency: str
    status: ReqStatus
    opened_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobListResponse(PaginatedResponse[JobRead]):
    pass
