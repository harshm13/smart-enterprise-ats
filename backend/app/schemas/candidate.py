import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.candidate import DegreeLevel, ParseStatus
from app.schemas.common import PaginatedResponse


class ResumeUploadResponse(BaseModel):
    task_id: str
    candidate_id: uuid.UUID
    resume_version_id: uuid.UUID
    file_name: str
    status: ParseStatus
    poll_url: str
    message: str


class ParseTaskStatusResponse(BaseModel):
    task_id: str
    status: str
    candidate_id: uuid.UUID | None = None
    error: str | None = None


class ResumeVersionRead(BaseModel):
    id: uuid.UUID
    file_name: str
    mime_type: str
    file_size_bytes: int | None
    is_latest: bool
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CandidateRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    full_name: str | None
    phone: str | None
    location: str | None
    linkedin_url: str | None
    portfolio_url: str | None
    skills: list[str]
    total_tenure_months: int | None
    current_title: str | None
    current_company: str | None
    highest_degree: DegreeLevel | None
    parse_status: ParseStatus
    parse_error: str | None
    parsed_profile: dict[str, Any]
    parsed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CandidateListResponse(PaginatedResponse[CandidateRead]):
    pass


class PresignedUrlRequest(BaseModel):
    file_name: str = Field(..., min_length=3, max_length=255)
    mime_type: str = Field(..., pattern=r"^(application/pdf|application/vnd\.openxmlformats-officedocument\.wordprocessingml\.document|text/plain)$")


class PresignedUrlResponse(BaseModel):
    upload_url: str
    method: str
    key: str
    headers: dict[str, str]
    expires_in_seconds: int
