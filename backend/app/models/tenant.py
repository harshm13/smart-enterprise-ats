import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.job import JobRequisition
    from app.models.candidate import Candidate
    from app.models.pipeline import PipelineTemplate


class PlanTier(str, enum.Enum):
    STARTER = "starter"
    GROWTH = "growth"
    ENTERPRISE = "enterprise"


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[PlanTier] = mapped_column(
        Enum(PlanTier, name="plan_tier"),
        nullable=False,
        default=PlanTier.STARTER,
        server_default=PlanTier.STARTER.value,
    )
    kms_key_arn: Mapped[str | None] = mapped_column(Text, nullable=True)
    settings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    sso_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Relationships ────────────────────────────────────────────────────────
    users: Mapped[list["User"]] = relationship(
        "User", back_populates="tenant", cascade="all, delete-orphan", lazy="select"
    )
    job_requisitions: Mapped[list["JobRequisition"]] = relationship(
        "JobRequisition", back_populates="tenant", cascade="all, delete-orphan", lazy="select"
    )
    candidates: Mapped[list["Candidate"]] = relationship(
        "Candidate", back_populates="tenant", cascade="all, delete-orphan", lazy="select"
    )
    pipeline_templates: Mapped[list["PipelineTemplate"]] = relationship(
        "PipelineTemplate", back_populates="tenant", cascade="all, delete-orphan", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Tenant id={self.id} slug={self.slug!r}>"
