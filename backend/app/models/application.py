import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.candidate import Candidate
    from app.models.job import JobRequisition
    from app.models.pipeline import PipelineStage


class AppStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    WITHDRAWN = "WITHDRAWN"
    REJECTED = "REJECTED"
    HIRED = "HIRED"


class Recommendation(str, enum.Enum):
    STRONG_YES = "STRONG_YES"
    YES = "YES"
    NEUTRAL = "NEUTRAL"
    NO = "NO"
    STRONG_NO = "STRONG_NO"


class Application(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id", "job_requisition_id", name="uq_application_candidate_job"
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("candidates.id"),
        nullable=False,
        index=True,
    )
    job_requisition_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("job_requisitions.id"),
        nullable=False,
        index=True,
    )
    current_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("pipeline_stages.id"),
        nullable=True,
    )

    # ── AI scoring ───────────────────────────────────────────────────────────
    ai_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    score_breakdown: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, server_default="{}"
    )
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Status ───────────────────────────────────────────────────────────────
    status: Mapped[AppStatus] = mapped_column(
        Enum(AppStatus, name="app_status"),
        nullable=False,
        default=AppStatus.ACTIVE,
        server_default=AppStatus.ACTIVE.value,
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    last_stage_change_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    hired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Relationships ────────────────────────────────────────────────────────
    tenant: Mapped["Tenant"] = relationship("Tenant")
    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="applications")
    job_requisition: Mapped["JobRequisition"] = relationship(
        "JobRequisition", back_populates="applications"
    )
    current_stage: Mapped["PipelineStage | None"] = relationship(
        "PipelineStage",
        back_populates="current_applications",
        foreign_keys=[current_stage_id],
    )
    events: Mapped[list["ApplicationEvent"]] = relationship(
        "ApplicationEvent",
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ApplicationEvent.created_at.desc()",
        lazy="select",
    )
    scorecards: Mapped[list["InterviewScorecard"]] = relationship(
        "InterviewScorecard",
        back_populates="application",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Application id={self.id} status={self.status.value} score={self.ai_score}>"


class ApplicationEvent(UUIDPrimaryKeyMixin, Base):
    """Immutable audit log — no updated_at column."""

    __tablename__ = "application_events"

    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    triggered_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    from_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("pipeline_stages.id"),
        nullable=True,
    )
    to_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("pipeline_stages.id"),
        nullable=True,
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSON, nullable=False, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # ── Relationships ────────────────────────────────────────────────────────
    application: Mapped["Application"] = relationship("Application", back_populates="events")
    triggered_by: Mapped["User | None"] = relationship(
        "User", back_populates="application_events", foreign_keys=[triggered_by_id]
    )
    from_stage: Mapped["PipelineStage | None"] = relationship(
        "PipelineStage", back_populates="from_events", foreign_keys=[from_stage_id]
    )
    to_stage: Mapped["PipelineStage | None"] = relationship(
        "PipelineStage", back_populates="to_events", foreign_keys=[to_stage_id]
    )

    def __repr__(self) -> str:
        return f"<ApplicationEvent id={self.id} type={self.event_type!r}>"


class InterviewScorecard(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "interview_scorecards"

    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    submitted_by_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    stage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("pipeline_stages.id"),
        nullable=False,
    )
    overall_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    responses: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    recommendation: Mapped[Recommendation | None] = mapped_column(
        Enum(Recommendation, name="recommendation"), nullable=True
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # ── Relationships ────────────────────────────────────────────────────────
    application: Mapped["Application"] = relationship("Application", back_populates="scorecards")
    submitted_by: Mapped["User"] = relationship("User", back_populates="scorecards")

    def __repr__(self) -> str:
        return f"<InterviewScorecard id={self.id} rating={self.overall_rating}>"
