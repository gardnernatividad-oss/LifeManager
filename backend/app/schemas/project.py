import enum
import unicodedata
import uuid

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import Project, ProjectStep


class ProjectState(str, enum.Enum):
    NO_INICIADO = "NO_INICIADO"
    EN_PROCESO = "EN_PROCESO"
    FINALIZADO = "FINALIZADO"


class StepCompliance(str, enum.Enum):
    EN_PLAZO = "EN_PLAZO"
    ATRASADO = "ATRASADO"
    CON_ADELANTO = "CON_ADELANTO"
    A_TIEMPO = "A_TIEMPO"
    CON_RETRASO = "CON_RETRASO"


def _clean_name(value: str) -> str:
    cleaned = unicodedata.normalize("NFC", " ".join(value.split()))
    if not cleaned:
        raise ValueError("name cannot be blank")
    if len(cleaned) > 255:
        raise ValueError("name must not exceed 255 characters")
    return cleaned


def derive_step_state(progress: int) -> ProjectState:
    if progress == 0:
        return ProjectState.NO_INICIADO
    if progress == 100:
        return ProjectState.FINALIZADO
    return ProjectState.EN_PROCESO


def derive_step_compliance(
    step: ProjectStep, *, local_date: date
) -> tuple[StepCompliance | None, int | None]:
    if step.planned_date is None:
        return None, None
    if step.completion_date is None:
        if step.planned_date >= local_date:
            return StepCompliance.EN_PLAZO, (step.planned_date - local_date).days
        return StepCompliance.ATRASADO, (local_date - step.planned_date).days
    if step.completion_date < step.planned_date:
        return StepCompliance.CON_ADELANTO, (
            step.planned_date - step.completion_date
        ).days
    if step.completion_date == step.planned_date:
        return StepCompliance.A_TIEMPO, 0
    return StepCompliance.CON_RETRASO, (
        step.completion_date - step.planned_date
    ).days


def derive_project_values(
    project: Project,
) -> tuple[date | None, Decimal | None, ProjectState | None, Decimal]:
    steps = list(project.steps)
    total_weight = sum((step.weight or Decimal("0") for step in steps), Decimal("0"))
    planned_dates = [step.planned_date for step in steps if step.planned_date is not None]
    planned_date = max(planned_dates) if planned_dates else None
    complete_structure = bool(steps) and all(
        step.planned_date is not None and step.weight is not None and step.weight > 0
        for step in steps
    ) and total_weight == Decimal("100.00")
    if not complete_structure:
        return planned_date, None, None, total_weight
    progress = sum(
        (step.weight * Decimal(step.progress) for step in steps if step.weight is not None),
        Decimal("0"),
    ) / Decimal("100")
    if all(step.progress == 0 for step in steps):
        state = ProjectState.NO_INICIADO
    elif all(step.progress == 100 for step in steps):
        state = ProjectState.FINALIZADO
    else:
        state = ProjectState.EN_PROCESO
    return planned_date, progress, state, total_weight


class ProjectStepCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    planned_date: date | None = None
    weight: Decimal | None = Field(default=None, gt=0, le=100, max_digits=5, decimal_places=2)
    position: int = Field(ge=0)

    _name = field_validator("name")(_clean_name)


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: uuid.UUID
    name: str
    is_active: bool
    steps: list[ProjectStepCreate] = Field(default_factory=list)

    _name = field_validator("name")(_clean_name)

    @field_validator("steps")
    @classmethod
    def positions_are_unique(cls, value: list[ProjectStepCreate]) -> list[ProjectStepCreate]:
        if len({step.position for step in value}) != len(value):
            raise ValueError("Step positions must be unique")
        return value


class ProjectPlanningUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: uuid.UUID | None = None
    name: str | None = None
    is_active: bool | None = None
    lock_version: int = Field(ge=1)

    @model_validator(mode="before")
    @classmethod
    def reject_nulls(cls, value: object) -> object:
        if isinstance(value, dict):
            for field in ("category_id", "name", "is_active"):
                if field in value and value[field] is None:
                    raise ValueError(f"{field} cannot be null")
        return value

    _name = field_validator("name")(_clean_name)

    @model_validator(mode="after")
    def require_change(self) -> "ProjectPlanningUpdate":
        if not (self.model_fields_set - {"lock_version"}):
            raise ValueError("At least one planning field is required")
        return self


class ProjectStepPlanningUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    planned_date: date | None = None
    weight: Decimal | None = Field(default=None, gt=0, le=100, max_digits=5, decimal_places=2)
    position: int | None = Field(default=None, ge=0)
    lock_version: int = Field(ge=1)

    @model_validator(mode="before")
    @classmethod
    def reject_null_non_nullable_fields(cls, value: object) -> object:
        if isinstance(value, dict):
            for field in ("name", "position"):
                if field in value and value[field] is None:
                    raise ValueError(f"{field} cannot be null")
        return value

    _name = field_validator("name")(_clean_name)

    @model_validator(mode="after")
    def require_change(self) -> "ProjectStepPlanningUpdate":
        if not (self.model_fields_set - {"lock_version"}):
            raise ValueError("At least one Step planning field is required")
        return self


class ProjectGeneralTrackingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    general_comment: str | None = None
    lock_version: int = Field(ge=1)

    @model_validator(mode="after")
    def require_change(self) -> "ProjectGeneralTrackingUpdate":
        if not (self.model_fields_set - {"lock_version"}):
            raise ValueError("At least one general tracking field is required")
        return self


class ProjectStepTrackingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    progress: int | None = Field(default=None, ge=0, le=100)
    comment: str | None = None
    lock_version: int = Field(ge=1)

    @model_validator(mode="before")
    @classmethod
    def reject_null_progress(cls, value: object) -> object:
        if isinstance(value, dict) and value.get("progress", ...) is None:
            raise ValueError("progress cannot be null")
        return value

    @model_validator(mode="after")
    def require_change(self) -> "ProjectStepTrackingUpdate":
        if not (self.model_fields_set - {"id", "lock_version"}):
            raise ValueError("At least one Step tracking field is required")
        return self


class ProjectTrackingBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_lock_version: int = Field(ge=1)
    items: list[ProjectStepTrackingUpdate] = Field(min_length=1)

    @field_validator("items")
    @classmethod
    def ids_are_unique(
        cls, value: list[ProjectStepTrackingUpdate]
    ) -> list[ProjectStepTrackingUpdate]:
        if len({item.id for item in value}) != len(value):
            raise ValueError("Project Step IDs must be unique")
        return value


class ProjectCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class ProjectStepRead(BaseModel):
    id: uuid.UUID
    name: str
    planned_date: date | None
    weight: Decimal | None
    progress: int
    state: ProjectState
    completion_date: date | None
    compliance: StepCompliance | None
    detail_days: int | None
    comment: str | None
    position: int
    lock_version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_step(cls, step: ProjectStep, *, local_date: date) -> "ProjectStepRead":
        compliance, detail_days = derive_step_compliance(step, local_date=local_date)
        return cls(
            id=step.id, name=step.name, planned_date=step.planned_date,
            weight=step.weight, progress=step.progress,
            state=derive_step_state(step.progress), completion_date=step.completion_date,
            compliance=compliance, detail_days=detail_days, comment=step.comment,
            position=step.position, lock_version=step.lock_version,
            created_at=step.created_at, updated_at=step.updated_at,
        )


class ProjectRead(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    category: ProjectCategoryRead
    name: str
    is_active: bool
    planned_date: date | None
    progress: Decimal | None
    state: ProjectState | None
    total_weight: Decimal
    general_comment: str | None
    last_tracking_saved_at: datetime | None
    lock_version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_project(cls, project: Project) -> "ProjectRead":
        planned_date, progress, state, total_weight = derive_project_values(project)
        return cls(
            id=project.id, category_id=project.category_id,
            category=ProjectCategoryRead.model_validate(project.category), name=project.name,
            is_active=project.is_active, planned_date=planned_date, progress=progress,
            state=state, total_weight=total_weight,
            general_comment=project.general_comment,
            last_tracking_saved_at=project.last_tracking_saved_at,
            lock_version=project.lock_version, created_at=project.created_at,
            updated_at=project.updated_at,
        )


class ProjectDetailRead(ProjectRead):
    steps: list[ProjectStepRead]

    @classmethod
    def from_project(cls, project: Project, *, local_date: date) -> "ProjectDetailRead":
        base = ProjectRead.from_project(project).model_dump()
        return cls(
            **base,
            steps=[ProjectStepRead.from_step(step, local_date=local_date) for step in project.steps],
        )


class ProjectListResponse(BaseModel):
    items: list[ProjectRead]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProjectTrackingBatchResponse(BaseModel):
    project: ProjectDetailRead
    saved_at: datetime
