import uuid
import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole


def _make_jwt(tenant_id: str, sub: str, role: str = "admin") -> str:
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
    role: UserRole = UserRole.ADMIN,
    sub: str | None = None,
) -> tuple[dict, User, str]:
    sub = sub or f"auth0|{uuid.uuid4().hex[:8]}"
    r = await client.post("/v1/tenants/", json={"slug": slug, "name": name})
    assert r.status_code == 201
    tenant_data = r.json()
    tenant_id = uuid.UUID(tenant_data["id"])

    user = User(
        tenant_id=tenant_id,
        email=f"admin@{slug}.com",
        full_name=f"{name} Admin",
        role=role,
        auth0_sub=sub,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    token = _make_jwt(str(tenant_id), sub, role.value)
    return tenant_data, user, token


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, db_session: AsyncSession) -> None:
    """GET /v1/users/me returns currently authenticated user profile."""
    _, user, token = await _create_tenant_and_user(
        client, db_session, slug="acme-me", name="Acme Me", role=UserRole.ADMIN
    )
    headers = {"Authorization": f"Bearer {token}"}

    res = await client.get("/v1/users/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == str(user.id)
    assert data["email"] == user.email
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_invite_and_list_users(client: AsyncClient, db_session: AsyncSession) -> None:
    """Admin can invite new users to tenant and list them."""
    _, admin, token = await _create_tenant_and_user(
        client, db_session, slug="globex-corp", name="Globex", role=UserRole.ADMIN
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Invite recruiter
    inv_res = await client.post(
        "/v1/users/",
        json={
            "email": "homer@globex.com",
            "full_name": "Homer Simpson",
            "role": "recruiter",
        },
        headers=headers,
    )
    assert inv_res.status_code == 201
    invited = inv_res.json()
    assert invited["email"] == "homer@globex.com"
    assert invited["role"] == "recruiter"

    # Duplicate email in same tenant fails with 409
    dup_res = await client.post(
        "/v1/users/",
        json={
            "email": "homer@globex.com",
            "full_name": "Homer Duplicate",
            "role": "interviewer",
        },
        headers=headers,
    )
    assert dup_res.status_code == 409

    # List users in tenant
    list_res = await client.get("/v1/users/", headers=headers)
    assert list_res.status_code == 200
    data = list_res.json()
    assert data["total"] == 2
    emails = [u["email"] for u in data["items"]]
    assert "admin@globex-corp.com" in emails
    assert "homer@globex.com" in emails


@pytest.mark.asyncio
async def test_update_and_deactivate_user(client: AsyncClient, db_session: AsyncSession) -> None:
    """Admin can update role and deactivate other users."""
    _, admin, token = await _create_tenant_and_user(
        client, db_session, slug="initech-corp", name="Initech", role=UserRole.ADMIN
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Invite user
    inv_res = await client.post(
        "/v1/users/",
        json={"email": "peter@initech.com", "full_name": "Peter Gibbons", "role": "recruiter"},
        headers=headers,
    )
    assert inv_res.status_code == 201
    user_id = inv_res.json()["id"]

    # Update role to interviewer
    patch_res = await client.patch(
        f"/v1/users/{user_id}",
        json={"role": "interviewer", "full_name": "Peter G."},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["role"] == "interviewer"
    assert patch_res.json()["full_name"] == "Peter G."

    # Deactivate user
    del_res = await client.delete(f"/v1/users/{user_id}", headers=headers)
    assert del_res.status_code == 204

    # Admin cannot deactivate self
    self_del = await client.delete(f"/v1/users/{admin.id}", headers=headers)
    assert self_del.status_code == 400


@pytest.mark.asyncio
async def test_user_tenant_isolation(client: AsyncClient, db_session: AsyncSession) -> None:
    """Admin of Tenant A cannot update or deactivate a user belonging to Tenant B."""
    _, admin_a, token_a = await _create_tenant_and_user(
        client, db_session, slug="tenant-a-users", name="Tenant A", role=UserRole.ADMIN
    )
    headers_a = {"Authorization": f"Bearer {token_a}"}

    _, admin_b, token_b = await _create_tenant_and_user(
        client, db_session, slug="tenant-b-users", name="Tenant B", role=UserRole.ADMIN
    )
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Invite user to Tenant B
    inv_b = await client.post(
        "/v1/users/",
        json={"email": "bob@tenant-b.com", "full_name": "Bob B", "role": "recruiter"},
        headers=headers_b,
    )
    assert inv_b.status_code == 201
    user_b_id = inv_b.json()["id"]

    # Admin A tries to modify user in Tenant B -> 404 (isolated)
    hack_res = await client.patch(
        f"/v1/users/{user_b_id}",
        json={"role": "admin"},
        headers=headers_a,
    )
    assert hack_res.status_code == 404

    # Admin A tries to deactivate user in Tenant B -> 404 (isolated)
    del_hack = await client.delete(f"/v1/users/{user_b_id}", headers=headers_a)
    assert del_hack.status_code == 404
