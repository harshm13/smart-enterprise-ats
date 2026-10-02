import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import current_tenant_id, get_db
from app.middleware.auth import get_current_user, require_role
from app.models.user import User, UserRole
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.user import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/v1/users", tags=["Users"])


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Return the currently authenticated user's profile."""
    return current_user


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def invite_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.RECRUITER)),
) -> User:
    """Invite a new user to the current tenant. Admin / Recruiter only."""
    tenant_id = current_tenant_id.get()
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenant context")

    existing = await db.execute(
        select(User).where(User.tenant_id == uuid.UUID(tenant_id), User.email == payload.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{payload.email}' already exists in this tenant.",
        )

    user = User(
        tenant_id=uuid.UUID(tenant_id),
        email=payload.email,
        full_name=payload.full_name,
        role=payload.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.get("/", response_model=PaginatedResponse[UserRead])
async def list_users(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.RECRUITER)),
) -> PaginatedResponse[UserRead]:
    """List all active users in the current tenant."""
    tenant_id = uuid.UUID(current_tenant_id.get())  # type: ignore[arg-type]

    total_result = await db.execute(
        select(func.count()).select_from(User).where(
            User.tenant_id == tenant_id, User.is_active.is_(True)
        )
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(User)
        .where(User.tenant_id == tenant_id, User.is_active.is_(True))
        .order_by(User.created_at.desc())
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    users = result.scalars().all()

    return PaginatedResponse(
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
        items=list(users),
    )


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> User:
    """Update a user's role or activation status. Admin only."""
    user = await db.get(User, user_id)
    if not user or user.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    await db.flush()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> None:
    """Deactivate (soft-delete) a user. Admin only."""
    user = await db.get(User, user_id)
    if not user or user.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account.",
        )
    user.is_active = False
    await db.flush()
