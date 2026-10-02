import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import StringArray, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.application import Application


class DegreeLevel(str, enum.Enum):
    HIGH_SCHOOL = "HIGH_SCHOOL"
    ASSOCIATES = "ASSOCIATES"
    BACHELORS = "BACHELORS"
    MASTERS = "MASTERS"
    PHD = "PHD"
    MBA = "MBA"
    BOOTCAMP_CERT = "BOOTCAMP_CERT"


class ParseStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Candidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "candidates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_candidates_tenant_email"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── NLP-extracted structured fields ─────────────────────────────────────
    skills: Mapped[list[str]] = mapped_column(
        StringArray, nullable=False, default=list
    )
    total_tenure_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    highest_degree: Mapped[DegreeLevel | None] = mapped_column(
        Enum(DegreeLevel, name="degree_level"), nullable=True
    )
    parsed_profile: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, server_default="{}"
    )

    # ── Vector reference ─────────────────────────────────────────────────────
    qdrant_point_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Parse state ──────────────────────────────────────────────────────────
    parse_status: Mapped[ParseStatus] = mapped_column(
        Enum(ParseStatus, name="parse_status"),
        nullable=False,
        default=ParseStatus.PENDING,
        server_default=ParseStatus.PENDING.value,
    )
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Relationships ────────────────────────────────────────────────────────
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="candidates")
    resume_versions: Mapped[list["ResumeVersion"]] = relationship(
        "ResumeVersion",
        back_populates="candidate",
        cascade="all, delete-orphan",
        order_by="ResumeVersion.uploaded_at.desc()",
        lazy="select",
    )
    applications: Mapped[list["Application"]] = relationship(
        "Application", back_populates="candidate", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Candidate id={self.id} email={self.email!r} status={self.parse_status.value}>"


class ResumeVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "resume_versions"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    s3_key: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_latest: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # ── Relationships ────────────────────────────────────────────────────────
    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="resume_versions")

    def __repr__(self) -> str:
        return f"<ResumeVersion id={self.id} file={self.file_name!r} latest={self.is_latest}>"
