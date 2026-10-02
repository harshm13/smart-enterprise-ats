import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.job import JobRequisition
    from app.models.application import Application, ApplicationEvent


class StageType(str, enum.Enum):
    APPLIED = "APPLIED"
    AI_SCREENING = "AI_SCREENING"
    PHONE_SCREEN = "PHONE_SCREEN"
    TECHNICAL_ASSESSMENT = "TECHNICAL_ASSESSMENT"
    ONSITE_INTERVIEW = "ONSITE_INTERVIEW"
    CULTURE_FIT = "CULTURE_FIT"
    OFFER_EXTENDED = "OFFER_EXTENDED"
    HIRED = "HIRED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class TriggerType(str, enum.Enum):
    EMAIL_CANDIDATE = "EMAIL_CANDIDATE"
    EMAIL_HIRING_TEAM = "EMAIL_HIRING_TEAM"
    WEBHOOK = "WEBHOOK"
    SCHEDULE_INTERVIEW = "SCHEDULE_INTERVIEW"
    SCORECARD_REQUEST = "SCORECARD_REQUEST"
    ADVANCE_STAGE = "ADVANCE_STAGE"


class PipelineTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pipeline_templates"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # ── Relationships ────────────────────────────────────────────────────────
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="pipeline_templates")
    stages: Mapped[list["PipelineStage"]] = relationship(
        "PipelineStage",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="PipelineStage.stage_order",
        lazy="select",
    )
    job_requisitions: Mapped[list["JobRequisition"]] = relationship(
        "JobRequisition", back_populates="pipeline_template", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<PipelineTemplate id={self.id} name={self.name!r}>"


class PipelineStage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "pipeline_stages"
    __table_args__ = (
        UniqueConstraint("template_id", "stage_order", name="uq_pipeline_stage_order"),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("pipeline_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    stage_order: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_type: Mapped[StageType] = mapped_column(
        Enum(StageType, name="stage_type"), nullable=False
    )
    sla_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_terminal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # ── Relationships ────────────────────────────────────────────────────────
    template: Mapped["PipelineTemplate"] = relationship("PipelineTemplate", back_populates="stages")
    triggers: Mapped[list["StageTrigger"]] = relationship(
        "StageTrigger", back_populates="stage", cascade="all, delete-orphan", lazy="select"
    )
    current_applications: Mapped[list["Application"]] = relationship(
        "Application", back_populates="current_stage", foreign_keys="Application.current_stage_id", lazy="select"
    )
    from_events: Mapped[list["ApplicationEvent"]] = relationship(
        "ApplicationEvent",
        back_populates="from_stage",
        foreign_keys="ApplicationEvent.from_stage_id",
        lazy="select",
    )
    to_events: Mapped[list["ApplicationEvent"]] = relationship(
        "ApplicationEvent",
        back_populates="to_stage",
        foreign_keys="ApplicationEvent.to_stage_id",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<PipelineStage id={self.id} name={self.name!r} order={self.stage_order}>"


class StageTrigger(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stage_triggers"

    stage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("pipeline_stages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trigger_type: Mapped[TriggerType] = mapped_column(
        Enum(TriggerType, name="trigger_type"), nullable=False
    )
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    delay_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    # ── Relationships ────────────────────────────────────────────────────────
    stage: Mapped["PipelineStage"] = relationship("PipelineStage", back_populates="triggers")

    def __repr__(self) -> str:
        return f"<StageTrigger id={self.id} type={self.trigger_type.value}>"
