import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.pipeline import StageType, TriggerType


class PipelineStageCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    stage_order: int = Field(..., ge=1)
    stage_type: StageType
    sla_days: int | None = Field(None, ge=1)
    is_terminal: bool = False

    model_config = ConfigDict(extra="forbid")


class PipelineStageUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    stage_order: int | None = Field(None, ge=1)
    sla_days: int | None = None
    is_terminal: bool | None = None

    model_config = ConfigDict(extra="forbid")


class StageTriggerCreate(BaseModel):
    trigger_type: TriggerType
    config: dict[str, Any] = Field(default_factory=dict)
    delay_minutes: int = Field(default=0, ge=0)

    model_config = ConfigDict(extra="forbid")


class StageTriggerRead(BaseModel):
    id: uuid.UUID
    stage_id: uuid.UUID
    trigger_type: TriggerType
    config: dict[str, Any]
    delay_minutes: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class PipelineStageRead(BaseModel):
    id: uuid.UUID
    template_id: uuid.UUID
    name: str
    stage_order: int
    stage_type: StageType
    sla_days: int | None
    is_terminal: bool
    triggers: list[StageTriggerRead] = []

    model_config = ConfigDict(from_attributes=True)


class PipelineTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    is_default: bool = False

    model_config = ConfigDict(extra="forbid")


class PipelineTemplateRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    is_default: bool
    stages: list[PipelineStageRead] = []

    model_config = ConfigDict(from_attributes=True)
