from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Query parameters for paginated list endpoints."""

    limit: int = 25
    offset: int = 0

    model_config = ConfigDict(extra="forbid")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standardised paginated response envelope."""

    total: int
    limit: int
    offset: int
    items: list[T]


class ErrorDetail(BaseModel):
    """RFC 7807 Problem Details error format."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str | None = None
