import uuid

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models import ProjectStage
from app.schemas.v2_project_stage import ProjectStageConfiguration, ProjectStageCreate, ProjectStageProgress, ProjectStageUpdate
from app.services.v2_project_stage import project_stage_summary, stage_projection


def test_stage_schemas_are_strict_and_weighted_projection_is_derived() -> None:
    created = ProjectStageCreate(name="  Preparar   cajas ", responsible_user_id=uuid.uuid4(), weight="40.00", planned_date=date(2026, 9, 10), project_lock_version=1)
    assert created.name == "Preparar cajas" and created.weight == Decimal("40.00")
    for payload in ({"name": "X", "weight": 0, "planned_date": "2026-09-10", "project_lock_version": 1}, {"name": "X", "position": 1, "weight": 40, "planned_date": "2026-09-10", "project_lock_version": 1}, {"name": "X", "weight": 40, "planned_date": "2026-09-10", "project_lock_version": 1, "workspace_id": str(uuid.uuid4())}):
        with pytest.raises(ValidationError):
            ProjectStageCreate.model_validate(payload)
    with pytest.raises(ValidationError):
        ProjectStageUpdate(lock_version=1, project_lock_version=1)
    with pytest.raises(ValidationError):
        ProjectStageProgress(progress=101, lock_version=1, project_lock_version=1)
    assert ProjectStageProgress(comment="  Seguimiento  ", lock_version=1, project_lock_version=1).comment == "Seguimiento"
    with pytest.raises(ValidationError):
        ProjectStageProgress(comment="   ", lock_version=1, project_lock_version=1)
    with pytest.raises(ValidationError):
        ProjectStageProgress(lock_version=1, project_lock_version=1)
    for total in ("99.99", "100.01"):
        with pytest.raises(ValidationError):
            ProjectStageConfiguration(items=[{"name": "Etapa", "weight": total, "planned_date": "2026-09-10"}], project_lock_version=1)
    assert ProjectStageConfiguration(items=[{"name": "Etapa", "weight": "100.00", "planned_date": "2026-09-10"}], project_lock_version=1).items[0].weight == Decimal("100.00")

    first = ProjectStage(name="A", position=1, weight=Decimal("40.00"), planned_date=date(2026, 9, 10), progress=Decimal("50.25"))
    second = ProjectStage(name="B", position=2, weight=Decimal("60.00"), planned_date=date(2026, 9, 12), progress=Decimal("100.00"), completion_date=date(2026, 9, 11))
    incomplete = project_stage_summary([first], local_date=date(2026, 9, 11))
    complete = project_stage_summary([first, second], local_date=date(2026, 9, 11))
    assert incomplete["weights_complete"] is False and incomplete["progress"] is None
    assert complete["progress"] == Decimal("80.10") and complete["state"] == "EN_PROCESO"
    assert project_stage_summary([], local_date=date(2026, 9, 11))["state"] == "NO_INICIADO"
    assert stage_projection(second, local_date=date(2026, 9, 12))[:3] == ("FINALIZADA", "CON_ADELANTO", 1)
