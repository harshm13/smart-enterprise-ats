import logging
import uuid
from functools import wraps
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import current_tenant_id, get_db
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/token", auto_error=False)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Validates the Bearer JWT and returns the authenticated User row.

    In Phase 1 the token is decoded without signature verification (acceptable
    for local development). Phase 5 will add JWKS-based RS256 verification
    against the Auth0 JWKS endpoint.
    """
    if token is None:
        raise _CREDENTIALS_EXCEPTION

    try:
        allowed_algorithms = list(set(settings.AUTH0_ALGORITHMS + ["HS256", "RS256"]))
        payload = jwt.decode(
            token,
            key="",
            options={
                "verify_signature": False,
                "verify_exp": False,
                "verify_aud": False,
            },
            algorithms=allowed_algorithms,
        )
    except JWTError as exc:
        logger.warning("JWT decode failed: %s", exc)
        raise _CREDENTIALS_EXCEPTION from exc

    auth0_sub: str | None = payload.get("sub")
    if not auth0_sub:
        raise _CREDENTIALS_EXCEPTION

    tenant_id = current_tenant_id.get()
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context could not be resolved from token",
        )

    try:
        tenant_uuid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant ID format",
        )

    result = await db.execute(
        select(User).where(
            User.auth0_sub == auth0_sub,
            User.tenant_id == tenant_uuid,
            User.is_active.is_(True),
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise _CREDENTIALS_EXCEPTION

    return user


def require_role(*roles: UserRole) -> Callable:
    """
    Dependency factory: enforces that the current user has one of the
    specified roles.  Usage::

        @router.get("/sensitive")
        async def sensitive(user: User = Depends(require_role(UserRole.ADMIN))):
            ...
    """
    async def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{current_user.role.value}' is not permitted. "
                    f"Required: {[r.value for r in roles]}"
                ),
            )
        return current_user

    return _dependency


# Convenience aliases
require_admin = require_role(UserRole.ADMIN)
require_recruiter_or_above = require_role(
    UserRole.ADMIN, UserRole.RECRUITER, UserRole.HIRING_MANAGER
)
require_any_authenticated = require_role(
    UserRole.ADMIN, UserRole.RECRUITER, UserRole.HIRING_MANAGER,
    UserRole.INTERVIEWER, UserRole.VIEWER,
)
