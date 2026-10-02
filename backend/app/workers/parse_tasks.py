import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.candidate import Candidate, DegreeLevel, ParseStatus, ResumeVersion
from app.services.nlp.extractor import extract_text
from app.services.nlp.parser import parse_resume
from app.services.storage import storage_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _parse_candidate_with_session(
    session: AsyncSession,
    candidate_id: uuid.UUID,
    resume_version_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> dict:
    cand_res = await session.execute(
        select(Candidate).where(Candidate.id == candidate_id, Candidate.tenant_id == tenant_id)
    )
    candidate = cand_res.scalar_one_or_none()

    ver_res = await session.execute(
        select(ResumeVersion).where(ResumeVersion.id == resume_version_id)
    )
    resume_ver = ver_res.scalar_one_or_none()

    if not candidate or not resume_ver:
        logger.error("Candidate %s or ResumeVersion %s not found", candidate_id, resume_version_id)
        raise ValueError(f"Candidate {candidate_id} or ResumeVersion {resume_version_id} not found")

    try:
        # 1. Update status to PROCESSING
        candidate.parse_status = ParseStatus.PROCESSING
        await session.flush()

        # 2. Download file
        file_bytes = storage_service.download_bytes(resume_ver.s3_key)

        # 3. Extract text
        raw_text = extract_text(file_bytes, resume_ver.file_name)

        # 4. Parse NLP
        parsed = parse_resume(raw_text)

        # 5. Update Candidate
        candidate.skills = parsed.get("skills", [])
        candidate.total_tenure_months = parsed.get("total_tenure_months")
        candidate.current_title = parsed.get("current_title")
        candidate.current_company = parsed.get("current_company")
        candidate.parsed_profile = parsed

        # Highest degree
        deg_val = parsed.get("highest_degree")
        if deg_val:
            try:
                candidate.highest_degree = DegreeLevel(deg_val)
            except ValueError:
                candidate.highest_degree = None

        # Fill missing contact info from parsed resume
        contact = parsed.get("contact", {})
        if not candidate.full_name and contact.get("full_name"):
            candidate.full_name = contact["full_name"]
        if not candidate.phone and contact.get("phone"):
            candidate.phone = contact["phone"]
        if not candidate.linkedin_url and contact.get("linkedin_url"):
            candidate.linkedin_url = contact["linkedin_url"]
        if not candidate.portfolio_url and contact.get("portfolio_url"):
            candidate.portfolio_url = contact["portfolio_url"]

        candidate.parse_status = ParseStatus.COMPLETED
        candidate.parsed_at = datetime.now(timezone.utc)
        candidate.parse_error = None
        await session.commit()

        logger.info("Successfully parsed resume for candidate %s (%d skills)", candidate.id, len(candidate.skills))
        return {
            "candidate_id": str(candidate.id),
            "status": "COMPLETED",
            "skills_count": len(candidate.skills),
        }

    except Exception as exc:
        logger.exception("Error parsing resume for candidate %s: %s", candidate_id, exc)
        candidate.parse_status = ParseStatus.FAILED
        candidate.parse_error = str(exc)
        await session.commit()
        raise


async def _async_parse_resume(
    candidate_id: uuid.UUID,
    resume_version_id: uuid.UUID,
    tenant_id: uuid.UUID,
    session: AsyncSession | None = None,
) -> dict:
    """
    Asynchronous resume parsing worker logic:
    1. Mark parse_status = PROCESSING
    2. Download resume bytes from StorageService
    3. Extract text (PDF/DOCX)
    4. Parse structured entities (skills, tenure, degrees, contact)
    5. Update candidate record with status = COMPLETED
    """
    if session is not None:
        return await _parse_candidate_with_session(session, candidate_id, resume_version_id, tenant_id)
    async with AsyncSessionLocal() as sess:
        return await _parse_candidate_with_session(sess, candidate_id, resume_version_id, tenant_id)


@celery_app.task(bind=True, name="app.workers.parse_tasks.parse_resume_task", max_retries=2)
def parse_resume_task(self, candidate_id_str: str, resume_version_id_str: str, tenant_id_str: str) -> dict:
    """
    Celery task wrapper to invoke async parsing in an isolated event loop.
    """
    candidate_id = uuid.UUID(candidate_id_str)
    resume_version_id = uuid.UUID(resume_version_id_str)
    tenant_id = uuid.UUID(tenant_id_str)

    try:
        return asyncio.run(_async_parse_resume(candidate_id, resume_version_id, tenant_id))
    except Exception as exc:
        logger.error("Celery task retry on error: %s", exc)
        raise self.retry(exc=exc, countdown=10)
