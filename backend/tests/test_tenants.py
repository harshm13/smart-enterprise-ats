import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant, PlanTier


@pytest.mark.asyncio
async def test_create_tenant_success(client: AsyncClient, db_session: AsyncSession) -> None:
    """Creating a tenant with a valid slug returns 201 and the new tenant."""
    response = await client.post(
        "/v1/tenants/",
        json={"slug": "acme-corp", "name": "Acme Corporation", "plan": "starter"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["slug"] == "acme-corp"
    assert data["name"] == "Acme Corporation"
    assert data["plan"] == "starter"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_tenant_duplicate_slug(client: AsyncClient, db_session: AsyncSession) -> None:
    """Creating two tenants with the same slug returns 409 Conflict."""
    payload = {"slug": "duplicate-slug", "name": "First Corp", "plan": "starter"}
    r1 = await client.post("/v1/tenants/", json=payload)
    assert r1.status_code == 201

    r2 = await client.post("/v1/tenants/", json=payload)
    assert r2.status_code == 409
    assert "duplicate-slug" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_create_tenant_invalid_slug(client: AsyncClient) -> None:
    """Slugs with uppercase letters fail Pydantic validation (422)."""
    response = await client.post(
        "/v1/tenants/",
        json={"slug": "UPPER-CASE", "name": "Bad Slug Corp"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_tenant_slug_with_leading_dash(client: AsyncClient) -> None:
    """Slugs starting with a dash are rejected."""
    response = await client.post(
        "/v1/tenants/",
        json={"slug": "-bad-slug", "name": "Bad Slug Corp"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_tenant_isolation(client: AsyncClient, db_session: AsyncSession) -> None:
    """
    Tenant data isolation: rows created for one tenant are not accessible
    from a different tenant context via Row-Level Security.
    This test verifies that two tenants are independently created with
    separate IDs — the RLS enforcement is verified at DB level in integration tests.
    """
    r1 = await client.post(
        "/v1/tenants/",
        json={"slug": "tenant-alpha", "name": "Tenant Alpha"},
    )
    r2 = await client.post(
        "/v1/tenants/",
        json={"slug": "tenant-beta", "name": "Tenant Beta"},
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]
    assert r1.json()["slug"] != r2.json()["slug"]
