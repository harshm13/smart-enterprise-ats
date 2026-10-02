import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import current_tenant_id, get_db
from app.middleware.auth import require_recruiter_or_above
from app.models.pipeline import PipelineStage, PipelineTemplate, StageTrigger
from app.models.user import User
from app.schemas.pipeline import (
    PipelineStageCreate,
    PipelineStageRead,
    PipelineStageUpdate,
    PipelineTemplateCreate,
    PipelineTemplateRead,
    StageTriggerCreate,
    StageTriggerRead,
)

router = APIRouter(prefix="/v1/pipeline-templates", tags=["Pipeline"])


def _assert_tenant(raw: str | None) -> uuid.UUID:
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenant context")
    return uuid.UUID(raw)


@router.post("/", response_model=PipelineTemplateRead, status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: PipelineTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_recruiter_or_above),
) -> PipelineTemplate:
    """Create a new pipeline template for the current tenant."""
    tenant_id = _assert_tenant(current_tenant_id.get())
    template = PipelineTemplate(
        tenant_id=tenant_id,
        name=payload.name,
        description=payload.description,
        is_default=payload.is_default,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template, attribute_names=["stages"])
    return template


@router.get("/", response_model=list[PipelineTemplateRead])
async def list_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_recruiter_or_above),
) -> list[PipelineTemplate]:
    """List all pipeline templates for the current tenant."""
    tenant_id = _assert_tenant(current_tenant_id.get())
    result = await db.execute(
        select(PipelineTemplate)
        .options(selectinload(PipelineTemplate.stages).selectinload(PipelineStage.triggers))
        .where(PipelineTemplate.tenant_id == tenant_id)
        .order_by(PipelineTemplate.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{template_id}", response_model=PipelineTemplateRead)
async def get_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_recruiter_or_above),
) -> PipelineTemplate:
    """Get a single pipeline template with all stages and triggers."""
    tenant_id = _assert_tenant(current_tenant_id.get())
    result = await db.execute(
        select(PipelineTemplate)
        .options(selectinload(PipelineTemplate.stages).selectinload(PipelineStage.triggers))
        .where(PipelineTemplate.id == template_id, PipelineTemplate.tenant_id == tenant_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return template


@router.post("/{template_id}/stages", response_model=PipelineStageRead, status_code=status.HTTP_201_CREATED)
async def add_stage(
    template_id: uuid.UUID,
    payload: PipelineStageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_recruiter_or_above),
) -> PipelineStage:
    """Add a new stage to a pipeline template."""
    tenant_id = _assert_tenant(current_tenant_id.get())
    template = await db.get(PipelineTemplate, template_id)
    if not template or template.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    stage = PipelineStage(
        template_id=template_id,
        name=payload.name,
        stage_order=payload.stage_order,
        stage_type=payload.stage_type,
        sla_days=payload.sla_days,
        is_terminal=payload.is_terminal,
    )
    db.add(stage)
    await db.flush()
    await db.refresh(stage, attribute_names=["triggers"])
    return stage


@router.patch("/stages/{stage_id}", response_model=PipelineStageRead)
async def update_stage(
    stage_id: uuid.UUID,
    payload: PipelineStageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_recruiter_or_above),
) -> PipelineStage:
    """Update a pipeline stage's properties."""
    tenant_id = _assert_tenant(current_tenant_id.get())
    stage = await db.get(PipelineStage, stage_id)
    if not stage:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stage not found")
    template = await db.get(PipelineTemplate, stage.template_id)
    if not template or template.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stage not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(stage, field, value)

    await db.flush()
    await db.refresh(stage, attribute_names=["triggers"])
    return stage


@router.delete("/stages/{stage_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stage(
    stage_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_recruiter_or_above),
) -> None:
    """Remove a stage from a pipeline template."""
    tenant_id = _assert_tenant(current_tenant_id.get())
    stage = await db.get(PipelineStage, stage_id)
    if not stage:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stage not found")
    template = await db.get(PipelineTemplate, stage.template_id)
    if not template or template.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stage not found")
    await db.delete(stage)
    await db.flush()


@router.post(
    "/stages/{stage_id}/triggers",
    response_model=StageTriggerRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_trigger(
    stage_id: uuid.UUID,
    payload: StageTriggerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_recruiter_or_above),
) -> StageTrigger:
    """Attach an automated trigger to a pipeline stage."""
    tenant_id = _assert_tenant(current_tenant_id.get())
    stage = await db.get(PipelineStage, stage_id)
    if not stage:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stage not found")
    template = await db.get(PipelineTemplate, stage.template_id)
    if not template or template.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stage not found")

    trigger = StageTrigger(
        stage_id=stage_id,
        trigger_type=payload.trigger_type,
        config=payload.config,
        delay_minutes=payload.delay_minutes,
    )
    db.add(trigger)
    await db.flush()
    await db.refresh(trigger)
    return trigger
