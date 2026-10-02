import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.pipeline import PipelineTemplate
    from app.models.application import Application


class EmploymentType(str, enum.Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"
    INTERNSHIP = "INTERNSHIP"


class ReqStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    PAUSED = "PAUSED"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class JobRequisition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "job_requisitions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    pipeline_template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("pipeline_templates.id"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employment_type: Mapped[EmploymentType | None] = mapped_column(
        Enum(EmploymentType, name="employment_type"), nullable=True
    )
    description_raw: Mapped[str] = mapped_column(Text, nullable=False)
    requirements: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD", server_default="USD")
    qdrant_point_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ReqStatus] = mapped_column(
        Enum(ReqStatus, name="req_status"),
        nullable=False,
        default=ReqStatus.DRAFT,
        server_default=ReqStatus.DRAFT.value,
    )
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Relationships ────────────────────────────────────────────────────────
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="job_requisitions")
    created_by_user: Mapped["User"] = relationship("User", back_populates="created_jobs")
    pipeline_template: Mapped["PipelineTemplate"] = relationship(
        "PipelineTemplate", back_populates="job_requisitions"
    )
    applications: Mapped[list["Application"]] = relationship(
        "Application", back_populates="job_requisition", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<JobRequisition id={self.id} title={self.title!r} status={self.status.value}>"
