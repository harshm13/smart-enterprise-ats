import uuid
import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

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
) -> tuple[dict, User, str]:
    sub = f"auth0|{uuid.uuid4().hex[:8]}"
    r = await client.post("/v1/tenants/", json={"slug": slug, "name": name})
    assert r.status_code == 201
    tenant_data = r.json()
    tenant_id = uuid.UUID(tenant_data["id"])

    user = User(
        tenant_id=tenant_id,
        email=f"recruiter@{slug}.com",
        full_name=f"{name} Recruiter",
        role=role,
        auth0_sub=sub,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    token = _make_jwt(str(tenant_id), sub, role.value)
    return tenant_data, user, token


@pytest.mark.asyncio
async def test_pipeline_template_crud_and_triggers(client: AsyncClient, db_session: AsyncSession) -> None:
    """Full pipeline management test: template -> stages -> triggers -> isolation."""
    _, user, token = await _create_tenant_and_user(
        client, db_session, slug="pipe-corp", name="Pipeline Corp"
    )
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create pipeline template
    t_res = await client.post(
        "/v1/pipeline-templates/",
        json={"name": "Software Engineering Track", "description": "5-stage technical hiring track", "is_default": True},
        headers=headers,
    )
    assert t_res.status_code == 201
    template = t_res.json()
    template_id = template["id"]
    assert template["name"] == "Software Engineering Track"

    # 2. Add Stage 1: AI_SCREENING
    s1_res = await client.post(
        f"/v1/pipeline-templates/{template_id}/stages",
        json={"name": "AI Resume Match", "stage_order": 1, "stage_type": "AI_SCREENING", "sla_days": 2},
        headers=headers,
    )
    assert s1_res.status_code == 201
    stage_1_id = s1_res.json()["id"]

    # 3. Add Stage 2: TECHNICAL_ASSESSMENT
    s2_res = await client.post(
        f"/v1/pipeline-templates/{template_id}/stages",
        json={"name": "Coding Test", "stage_order": 2, "stage_type": "TECHNICAL_ASSESSMENT", "sla_days": 5},
        headers=headers,
    )
    assert s2_res.status_code == 201
    stage_2_id = s2_res.json()["id"]

    # 4. Attach trigger to Stage 2 (Auto-email candidate)
    trig_res = await client.post(
        f"/v1/pipeline-templates/stages/{stage_2_id}/triggers",
        json={
            "trigger_type": "EMAIL_CANDIDATE",
            "config": {"template": "invite_assessment", "platform": "HackerRank"},
            "delay_minutes": 10,
        },
        headers=headers,
    )
    assert trig_res.status_code == 201
    trigger = trig_res.json()
    assert trigger["trigger_type"] == "EMAIL_CANDIDATE"
    assert trigger["delay_minutes"] == 10

    # 5. Get template with all stages
    get_t = await client.get(f"/v1/pipeline-templates/{template_id}", headers=headers)
    assert get_t.status_code == 200
    t_data = get_t.json()
    assert len(t_data["stages"]) == 2
    assert t_data["stages"][1]["triggers"][0]["trigger_type"] == "EMAIL_CANDIDATE"

    # 6. Update Stage 1 SLA
    patch_s = await client.patch(
        f"/v1/pipeline-templates/stages/{stage_1_id}",
        json={"sla_days": 1, "name": "Instant AI Screen"},
        headers=headers,
    )
    assert patch_s.status_code == 200
    assert patch_s.json()["sla_days"] == 1

    # 7. Delete Stage 1
    del_s = await client.delete(f"/v1/pipeline-templates/stages/{stage_1_id}", headers=headers)
    assert del_s.status_code == 204

    # Verify Stage 1 is gone
    get_after_del = await client.get(f"/v1/pipeline-templates/{template_id}", headers=headers)
    assert len(get_after_del.json()["stages"]) == 1


@pytest.mark.asyncio
async def test_pipeline_cross_tenant_isolation(client: AsyncClient, db_session: AsyncSession) -> None:
    """User in Tenant A cannot see or modify templates in Tenant B."""
    _, _, token_a = await _create_tenant_and_user(client, db_session, slug="pipe-a", name="Pipe A")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    _, _, token_b = await _create_tenant_and_user(client, db_session, slug="pipe-b", name="Pipe B")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Tenant A creates template
    res_a = await client.post(
        "/v1/pipeline-templates/",
        json={"name": "Confidential Template A"},
        headers=headers_a,
    )
    assert res_a.status_code == 201
    template_a_id = res_a.json()["id"]

    # Tenant B tries to get Tenant A template -> 404
    get_b = await client.get(f"/v1/pipeline-templates/{template_a_id}", headers=headers_b)
    assert get_b.status_code == 404

    # Tenant B lists templates -> Tenant A's template is not listed
    list_b = await client.get("/v1/pipeline-templates/", headers=headers_b)
    assert list_b.status_code == 200
    assert len(list_b.json()) == 0
