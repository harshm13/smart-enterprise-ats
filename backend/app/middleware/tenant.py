import logging

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.database import current_tenant_id

logger = logging.getLogger(__name__)

# Routes that do NOT require a tenant context
_PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/v1/tenants"}


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Extracts tenant context from the JWT `org_id` claim on every request.

    - Sets the `current_tenant_id` ContextVar consumed by `get_db()`.
    - Appends `X-Tenant-ID` header to responses for debugging.
    - Passes through unauthenticated requests to public routes without error;
      protected routes will fail at the RBAC dependency layer instead.
    """

    async def dispatch(self, request: Request, call_next: type) -> Response:
        tenant: str | None = None

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer "):]
            try:
                # Decode without full signature verification at the middleware layer.
                # Full JWKS verification is handled in the auth dependency (auth.py).
                # We only need the claims here to set the tenant context early.
                payload = jwt.decode(
                    token,
                    key="",  # no-op key — verification skipped intentionally
                    options={
                        "verify_signature": False,
                        "verify_exp": False,
                        "verify_aud": False,
                    },
                    algorithms=["RS256", "HS256"],
                )
                # Auth0 uses `org_id` for organization/tenant; fall back to `sub`
                tenant = payload.get("org_id") or payload.get("tenant_id")
            except JWTError:
                logger.debug("TenantMiddleware: could not decode JWT — skipping tenant context")

        token_ctx = current_tenant_id.set(tenant)
        try:
            response: Response = await call_next(request)
        finally:
            current_tenant_id.reset(token_ctx)

        if tenant:
            response.headers["X-Tenant-ID"] = tenant

        return response
