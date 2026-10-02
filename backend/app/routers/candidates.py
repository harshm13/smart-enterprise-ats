import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import current_tenant_id, get_db
from app.middleware.auth import get_current_user, require_recruiter_or_above
from app.models.candidate import Candidate, ParseStatus
from app.models.user import User
from app.schemas.candidate import CandidateListResponse, CandidateRead
from app.schemas.common import PaginationParams

router = APIRouter(prefix="/v1/candidates", tags=["Candidates"])


def _assert_tenant(raw: str | None) -> uuid.UUID:
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenant context")
    return uuid.UUID(raw)


@router.get("/", response_model=CandidateListResponse)
async def list_candidates(
    pagination: PaginationParams = Depends(),
    skills: str | None = Query(None, description="Comma-separated skill filter (e.g. 'Python,FastAPI')"),
    parse_status: ParseStatus | None = Query(None, alias="status"),
    search: str | None = Query(None, description="Search by candidate name or email"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_recruiter_or_above),
) -> CandidateListResponse:
    """List candidates for current tenant with skill and status filters."""
    tenant_id = _assert_tenant(current_tenant_id.get())

    filters = [Candidate.tenant_id == tenant_id]
    if parse_status:
        filters.append(Candidate.parse_status == parse_status)
    if search:
        search_filter = f"%{search}%"
        filters.append(
            (Candidate.full_name.ilike(search_filter)) | (Candidate.email.ilike(search_filter))
        )

    # Count
    total_res = await db.execute(select(func.count()).select_from(Candidate).where(*filters))
    total = total_res.scalar_one()

    # Query items
    query = (
        select(Candidate)
        .where(*filters)
        .order_by(Candidate.created_at.desc())
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    items_res = await db.execute(query)
    candidates = list(items_res.scalars().all())

    # In-memory skill filtering if skills query param provided
    if skills:
        required_skills = {s.strip().lower() for s in skills.split(",") if s.strip()}
        candidates = [
            c for c in candidates
            if required_skills.issubset({s.lower() for s in (c.skills or [])})
        ]

    return CandidateListResponse(
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
        items=candidates,
    )


@router.get("/{candidate_id}", response_model=CandidateRead)
async def get_candidate(
    candidate_id: uuid.UUID,
    blind: bool = Query(False, description="Return demographically redacted profile for blind screening"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Candidate:
    """Retrieve full candidate profile, optionally returning demographically blind view for bias mitigation."""
    tenant_id = _assert_tenant(current_tenant_id.get())
    candidate = await db.get(Candidate, candidate_id)
    if not candidate or candidate.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    if blind and candidate.parsed_profile and "blind_view" in candidate.parsed_profile:
        # Create sanitized copy for response
        blind_view = candidate.parsed_profile["blind_view"]
        candidate.full_name = blind_view.get("full_name", "[REDACTED]")
        candidate.email = "[REDACTED]"
        candidate.phone = "[REDACTED]"
        candidate.location = "[REDACTED]"
        candidate.linkedin_url = None
        candidate.portfolio_url = None

    return candidate


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate(
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_recruiter_or_above),
) -> None:
    """Delete a candidate and their resume versions (GDPR / right to be forgotten)."""
    tenant_id = _assert_tenant(current_tenant_id.get())
    candidate = await db.get(Candidate, candidate_id)
    if not candidate or candidate.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    await db.delete(candidate)
    await db.flush()
