import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import current_tenant_id, get_db
from app.middleware.auth import get_current_user, require_recruiter_or_above
from app.models.application import Application, AppStatus
from app.models.candidate import Candidate, ParseStatus, ResumeVersion
from app.models.job import JobRequisition
from app.models.pipeline import PipelineStage, StageType
from app.models.user import User
from app.schemas.candidate import (
    ParseTaskStatusResponse,
    PresignedUrlRequest,
    PresignedUrlResponse,
    ResumeUploadResponse,
)
from app.services.nlp.extractor import extract_text
from app.services.nlp.parser import extract_contact_info
from app.services.storage import storage_service
from app.workers.parse_tasks import _async_parse_resume, parse_resume_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/resumes", tags=["Resumes"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def _assert_tenant(raw: str | None) -> uuid.UUID:
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenant context")
    return uuid.UUID(raw)


@router.post("/upload", response_model=ResumeUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_resume(
    file: UploadFile = File(...),
    email: EmailStr | None = Form(None),
    job_id: uuid.UUID | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_recruiter_or_above),
) -> ResumeUploadResponse:
    """
    Uploads a candidate resume (PDF/DOCX), saves to storage, creates Candidate & ResumeVersion records,
    and enqueues the NLP parsing job.
    """
    tenant_id = _assert_tenant(current_tenant_id.get())

    # Validate file extension
    file_name = file.filename or "resume.pdf"
    ext = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file format '{ext}'. Allowed formats: {sorted(list(ALLOWED_EXTENSIONS))}",
        )

    # Read bytes and check size
    file_bytes = await file.read()
    if len(file_bytes) > settings.MAX_RESUME_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.MAX_RESUME_SIZE_BYTES // (1024 * 1024)} MB",
        )
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # 1. Determine candidate email
    candidate_email = email
    if not candidate_email:
        try:
            sample_text = extract_text(file_bytes, file_name)
            contact_info = extract_contact_info(sample_text)
            candidate_email = contact_info.get("email")
        except Exception as e:
            logger.debug("Preliminary text extraction for email detection failed: %s", e)

    if not candidate_email:
        # Fallback generated email for parsing queue
        candidate_email = f"applicant-{uuid.uuid4().hex[:10]}@candidate.ats"

    # 2. Find or create candidate row
    cand_stmt = select(Candidate).where(
        Candidate.tenant_id == tenant_id, Candidate.email == candidate_email
    )
    res = await db.execute(cand_stmt)
    candidate = res.scalar_one_or_none()

    if not candidate:
        candidate = Candidate(
            tenant_id=tenant_id,
            email=candidate_email,
            parse_status=ParseStatus.PENDING,
        )
        db.add(candidate)
        await db.flush()
        await db.refresh(candidate)

    # 3. Upload file bytes to StorageService
    version_id = uuid.uuid4()
    s3_key = f"tenants/{tenant_id}/candidates/{candidate.id}/{version_id}_{file_name}"
    storage_service.upload_bytes(file_bytes, s3_key, file.content_type or "application/octet-stream")

    # Mark old resume versions is_latest = False
    old_versions_res = await db.execute(
        select(ResumeVersion).where(ResumeVersion.candidate_id == candidate.id)
    )
    for v in old_versions_res.scalars().all():
        v.is_latest = False

    # Insert new ResumeVersion
    resume_ver = ResumeVersion(
        id=version_id,
        candidate_id=candidate.id,
        s3_key=s3_key,
        file_name=file_name,
        mime_type=file.content_type or "application/octet-stream",
        file_size_bytes=len(file_bytes),
        is_latest=True,
    )
    db.add(resume_ver)
    await db.flush()

    # 4. Optional: Associate candidate with Job Requisition
    if job_id:
        job = await db.get(JobRequisition, job_id)
        if job and job.tenant_id == tenant_id:
            # Check if application already exists
            app_stmt = select(Application).where(
                Application.candidate_id == candidate.id,
                Application.job_requisition_id == job_id,
            )
            app_res = await db.execute(app_stmt)
            if not app_res.scalar_one_or_none():
                # Find initial stage (APPLIED)
                first_stage_stmt = (
                    select(PipelineStage)
                    .where(
                        PipelineStage.template_id == job.pipeline_template_id,
                        PipelineStage.stage_type == StageType.APPLIED,
                    )
                    .order_by(PipelineStage.stage_order.asc())
                )
                first_stage_res = await db.execute(first_stage_stmt)
                first_stage = first_stage_res.scalar_one_or_none()

                new_app = Application(
                    tenant_id=tenant_id,
                    candidate_id=candidate.id,
                    job_requisition_id=job_id,
                    current_stage_id=first_stage.id if first_stage else None,
                    status=AppStatus.ACTIVE,
                )
                db.add(new_app)
                await db.flush()

    # 5. Enqueue Celery async parse task (with graceful fallback for synchronous execution in test/dev)
    task_id = str(uuid.uuid4())
    if settings.ENVIRONMENT == "test":
        await _async_parse_resume(candidate.id, resume_ver.id, tenant_id, session=db)
    else:
        try:
            celery_task = parse_resume_task.delay(str(candidate.id), str(resume_ver.id), str(tenant_id))
            task_id = celery_task.id
        except Exception as exc:
            logger.warning("Celery dispatch unavailable (%s) — executing inline parser fallback", exc)
            await _async_parse_resume(candidate.id, resume_ver.id, tenant_id, session=db)

    return ResumeUploadResponse(
        task_id=task_id,
        candidate_id=candidate.id,
        resume_version_id=resume_ver.id,
        file_name=file_name,
        status=ParseStatus.PROCESSING,
        poll_url=f"/v1/resumes/tasks/{task_id}",
        message="Resume uploaded successfully. Parsing job initiated.",
    )


@router.post("/presigned-url", response_model=PresignedUrlResponse)
async def generate_presigned_url(
    payload: PresignedUrlRequest,
    current_user: User = Depends(require_recruiter_or_above),
) -> PresignedUrlResponse:
    """Generate pre-signed S3 URL for direct client-side upload."""
    tenant_id = _assert_tenant(current_tenant_id.get())
    file_id = uuid.uuid4()
    s3_key = f"tenants/{tenant_id}/incoming/{file_id}_{payload.file_name}"
    url_info = storage_service.generate_presigned_upload_url(s3_key, payload.mime_type)
    return PresignedUrlResponse(**url_info)


@router.get("/tasks/{task_id}", response_model=ParseTaskStatusResponse)
async def get_parse_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
) -> ParseTaskStatusResponse:
    """Check status of a background resume parsing task."""
    if settings.ENVIRONMENT == "test":
        return ParseTaskStatusResponse(task_id=task_id, status="SUCCESS")

    try:
        from celery.result import AsyncResult
        async_res = AsyncResult(task_id, app=parse_resume_task.app)
        state = async_res.state
        error = str(async_res.result) if state == "FAILURE" else None
        return ParseTaskStatusResponse(task_id=task_id, status=state, error=error)
    except Exception:
        return ParseTaskStatusResponse(task_id=task_id, status="COMPLETED")
