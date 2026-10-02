import uuid
import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant, PlanTier
from app.models.user import User, UserRole


def _make_jwt(tenant_id: str, sub: str, role: str = "recruiter") -> str:
    return jwt.encode(
        {"sub": sub, "org_id": tenant_id, "role": role},
        key="secret",
        algorithm="HS256",
    )


async def _create_tenant_and_user(
    client: AsyncClient,
    db_session: AsyncSession,
    slug: str,
    name: str,
    role: UserRole = UserRole.RECRUITER,
    sub: str | None = None,
) -> tuple[dict, User, str]:
    sub = sub or f"auth0|{uuid.uuid4().hex[:8]}"
    r = await client.post("/v1/tenants/", json={"slug": slug, "name": name})
    assert r.status_code == 201
    tenant_data = r.json()
    tenant_id = uuid.UUID(tenant_data["id"])

    user = User(
        tenant_id=tenant_id,
        email=f"{slug}@example.com",
        full_name=f"{name} User",
        role=role,
        auth0_sub=sub,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    token = _make_jwt(str(tenant_id), sub, role.value)
    return tenant_data, user, token


@pytest.mark.asyncio
async def test_create_job_requires_auth(client: AsyncClient, db_session: AsyncSession) -> None:
    """Creating a job without a JWT returns 401."""
    response = await client.post(
        "/v1/jobs/",
        json={
            "title": "Senior Engineer",
            "description_raw": "We need a Senior Engineer with 5+ years of experience in distributed systems.",
            "pipeline_template_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_jobs_empty(client: AsyncClient, db_session: AsyncSession) -> None:
    """List jobs returns 401 when unauthenticated."""
    response = await client.get("/v1/jobs/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_job_not_found(client: AsyncClient, db_session: AsyncSession) -> None:
    """GET on a non-existent job ID returns 401 when unauthenticated."""
    response = await client.get(f"/v1/jobs/{uuid.uuid4()}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_job_full_lifecycle(client: AsyncClient, db_session: AsyncSession) -> None:
    """End-to-end test: create tenant, pipeline, recruiter, create job, patch, publish, and close."""
    _, user, token = await _create_tenant_and_user(
        client, db_session, slug="hooli-corp", name="Hooli Corp", role=UserRole.RECRUITER
    )
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create pipeline template
    t_res = await client.post(
        "/v1/pipeline-templates/",
        json={"name": "Standard Engineering", "is_default": True},
        headers=headers,
    )
    assert t_res.status_code == 201
    template_id = t_res.json()["id"]

    # 2. Create job requisition (status: DRAFT)
    job_payload = {
        "title": "Lead Backend Architect",
        "department": "Core Platform",
        "location": "San Francisco, CA (Hybrid)",
        "employment_type": "FULL_TIME",
        "description_raw": "We are looking for a Lead Backend Architect with 8+ years experience in Python, FastAPI, and PostgreSQL.",
        "requirements": [
            {"skill": "Python", "required": True, "weight": 1.0},
            {"skill": "FastAPI", "required": True, "weight": 0.8},
            {"skill": "PostgreSQL", "required": True, "weight": 0.9},
        ],
        "salary_min": 180000,
        "salary_max": 240000,
        "currency": "USD",
        "pipeline_template_id": template_id,
    }
    j_res = await client.post("/v1/jobs/", json=job_payload, headers=headers)
    assert j_res.status_code == 201
    job = j_res.json()
    job_id = job["id"]
    assert job["status"] == "DRAFT"
    assert job["title"] == "Lead Backend Architect"
    assert len(job["requirements"]) == 3

    # 3. Read single job
    get_res = await client.get(f"/v1/jobs/{job_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == job_id

    # 4. Patch job
    patch_res = await client.patch(
        f"/v1/jobs/{job_id}",
        json={"title": "Principal Backend Architect", "salary_max": 260000},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Principal Backend Architect"
    assert patch_res.json()["salary_max"] == 260000

    # 5. Publish job (DRAFT -> OPEN)
    pub_res = await client.post(f"/v1/jobs/{job_id}/publish", headers=headers)
    assert pub_res.status_code == 200
    assert pub_res.json()["status"] == "OPEN"
    assert pub_res.json()["opened_at"] is not None

    # Cannot re-publish already OPEN job
    repub_res = await client.post(f"/v1/jobs/{job_id}/publish", headers=headers)
    assert repub_res.status_code == 409

    # 6. Close job (OPEN -> CLOSED)
    close_res = await client.post(f"/v1/jobs/{job_id}/close", headers=headers)
    assert close_res.status_code == 200
    assert close_res.json()["status"] == "CLOSED"
    assert close_res.json()["closed_at"] is not None


@pytest.mark.asyncio
async def test_job_rbac_interviewer_forbidden(client: AsyncClient, db_session: AsyncSession) -> None:
    """Users with INTERVIEWER role cannot create or publish jobs (403 Forbidden)."""
    _, user, token = await _create_tenant_and_user(
        client, db_session, slug="pied-piper", name="Pied Piper", role=UserRole.INTERVIEWER
    )
    headers = {"Authorization": f"Bearer {token}"}

    res = await client.post(
        "/v1/jobs/",
        json={
            "title": "Systems Engineer",
            "description_raw": "Seeking low-level systems programmer with C++ and Linux kernel skills.",
            "pipeline_template_id": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert res.status_code == 403
    assert "not permitted" in res.json()["detail"]


@pytest.mark.asyncio
async def test_job_cross_tenant_isolation(client: AsyncClient, db_session: AsyncSession) -> None:
    """User in Tenant A cannot view, update, publish, or close a job belonging to Tenant B."""
    # Tenant Alpha
    t_a, _, token_a = await _create_tenant_and_user(
        client, db_session, slug="tenant-alpha-corp", name="Alpha Corp", role=UserRole.RECRUITER
    )
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Create Template in Tenant A
    t_res = await client.post(
        "/v1/pipeline-templates/",
        json={"name": "Alpha Template", "is_default": True},
        headers=headers_a,
    )
    assert t_res.status_code == 201
    template_id = t_res.json()["id"]

    # Create Job in Tenant A
    j_res = await client.post(
        "/v1/jobs/",
        json={
            "title": "Alpha Secret Project Lead",
            "description_raw": "Confidential role building next-gen quantum infrastructure systems.",
            "pipeline_template_id": template_id,
        },
        headers=headers_a,
    )
    assert j_res.status_code == 201
    job_id = j_res.json()["id"]

    # Tenant Beta
    t_b, _, token_b = await _create_tenant_and_user(
        client, db_session, slug="tenant-beta-corp", name="Beta Corp", role=UserRole.RECRUITER
    )
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Tenant B tries to GET Tenant A's job -> 404 Not Found (tenant-isolated)
    get_res = await client.get(f"/v1/jobs/{job_id}", headers=headers_b)
    assert get_res.status_code == 404

    # Tenant B tries to PATCH Tenant A's job -> 404 Not Found
    patch_res = await client.patch(
        f"/v1/jobs/{job_id}",
        json={"title": "Hacked Title"},
        headers=headers_b,
    )
    assert patch_res.status_code == 404

    # Tenant B lists jobs -> Tenant A's job is NOT present in Tenant B's list
    list_res = await client.get("/v1/jobs/", headers=headers_b)
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 0
    assert len(list_res.json()["items"]) == 0

