import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import current_tenant_id, get_db
from app.middleware.auth import get_current_user, require_recruiter_or_above
from app.models.job import JobRequisition, ReqStatus
from app.models.user import User
from app.schemas.common import PaginationParams
from app.schemas.job import JobCreate, JobListResponse, JobRead, JobUpdate

router = APIRouter(prefix="/v1/jobs", tags=["Jobs"])


def _assert_tenant(raw: str | None) -> uuid.UUID:
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenant context")
    return uuid.UUID(raw)


@router.post("/", response_model=JobRead, status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: JobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_recruiter_or_above),
) -> JobRequisition:
    """Create a new job requisition (default status: DRAFT)."""
    tenant_id = _assert_tenant(current_tenant_id.get())

    job = JobRequisition(
        tenant_id=tenant_id,
        created_by_id=current_user.id,
        pipeline_template_id=payload.pipeline_template_id,
        title=payload.title,
        department=payload.department,
        location=payload.location,
        employment_type=payload.employment_type,
        description_raw=payload.description_raw,
        requirements=[r.model_dump() for r in payload.requirements],
        salary_min=payload.salary_min,
        salary_max=payload.salary_max,
        currency=payload.currency,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    return job


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    pagination: PaginationParams = Depends(),
    status_filter: ReqStatus | None = Query(None, alias="status"),
    department: str | None = Query(None),
    search: str | None = Query(None, description="Full-text search on job title"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_recruiter_or_above),
) -> JobListResponse:
    """List job requisitions for the current tenant with optional filters."""
    tenant_id = _assert_tenant(current_tenant_id.get())

    filters = [JobRequisition.tenant_id == tenant_id]
    if status_filter:
        filters.append(JobRequisition.status == status_filter)
    if department:
        filters.append(JobRequisition.department.ilike(f"%{department}%"))
    if search:
        filters.append(JobRequisition.title.ilike(f"%{search}%"))

    total_result = await db.execute(
        select(func.count()).select_from(JobRequisition).where(*filters)
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(JobRequisition)
        .where(*filters)
        .order_by(JobRequisition.created_at.desc())
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    jobs = result.scalars().all()

    return JobListResponse(
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
        items=list(jobs),
    )


@router.get("/{job_id}", response_model=JobRead)
async def get_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobRequisition:
    """Fetch a single job requisition by ID."""
    tenant_id = _assert_tenant(current_tenant_id.get())
    job = await db.get(JobRequisition, job_id)
    if not job or job.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.patch("/{job_id}", response_model=JobRead)
async def update_job(
    job_id: uuid.UUID,
    payload: JobUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_recruiter_or_above),
) -> JobRequisition:
    """Update a job requisition (patch semantics — only provided fields are changed)."""
    tenant_id = _assert_tenant(current_tenant_id.get())
    job = await db.get(JobRequisition, job_id)
    if not job or job.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status == ReqStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Archived jobs cannot be modified."
        )

    update_data = payload.model_dump(exclude_unset=True)
    if "requirements" in update_data and update_data["requirements"] is not None:
        update_data["requirements"] = [
            r.model_dump() if hasattr(r, "model_dump") else r
            for r in update_data["requirements"]
        ]
    for field, value in update_data.items():
        setattr(job, field, value)

    await db.flush()
    await db.refresh(job)
    return job


@router.post("/{job_id}/publish", response_model=JobRead)
async def publish_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_recruiter_or_above),
) -> JobRequisition:
    """Transition a DRAFT job to OPEN, making it visible for applications."""
    tenant_id = _assert_tenant(current_tenant_id.get())
    job = await db.get(JobRequisition, job_id)
    if not job or job.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status != ReqStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is '{job.status.value}' — only DRAFT jobs can be published.",
        )
    job.status = ReqStatus.OPEN
    job.opened_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(job)
    return job


@router.post("/{job_id}/close", response_model=JobRead)
async def close_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_recruiter_or_above),
) -> JobRequisition:
    """Close an OPEN or PAUSED job requisition."""
    tenant_id = _assert_tenant(current_tenant_id.get())
    job = await db.get(JobRequisition, job_id)
    if not job or job.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status not in (ReqStatus.OPEN, ReqStatus.PAUSED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is '{job.status.value}' — only OPEN or PAUSED jobs can be closed.",
        )
    job.status = ReqStatus.CLOSED
    job.closed_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(job)
    return job
