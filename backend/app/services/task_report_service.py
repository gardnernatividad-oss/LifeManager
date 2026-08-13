import uuid

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, MasterTask, Task, TaskResult
from app.schemas.task_report import (
    TaskMasterTaskReportRow,
    TaskOutcomeMetrics,
    TaskReportPeriod,
    TaskReportResponse,
)


class TaskReportMasterTaskNotFoundError(LookupError):
    pass


class TaskReportCategoryNotFoundError(LookupError):
    pass


def _completion_rate(completed: int, terminal: int) -> Decimal | None:
    if terminal == 0:
        return None
    return (
        Decimal(completed) * Decimal("100") / Decimal(terminal)
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_task_report(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    planned_from: date | None = None,
    planned_to: date | None = None,
    master_task_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
) -> TaskReportResponse:
    master_task: MasterTask | None = None
    if master_task_id is not None:
        master_task = db.scalar(
            select(MasterTask).where(
                MasterTask.id == master_task_id,
                MasterTask.workspace_id == workspace_id,
            )
        )
        if master_task is None:
            raise TaskReportMasterTaskNotFoundError("Master task not found")
    if category_id is not None:
        category_exists = db.scalar(
            select(Category.id).where(
                Category.id == category_id,
                Category.workspace_id == workspace_id,
            )
        )
        if category_exists is None:
            raise TaskReportCategoryNotFoundError("Category not found")
        if master_task is not None and master_task.category_id != category_id:
            raise TaskReportMasterTaskNotFoundError("Master task not found")

    filters = [Task.workspace_id == workspace_id]
    if planned_from is not None:
        filters.append(Task.planned_date >= planned_from)
    if planned_to is not None:
        filters.append(Task.planned_date <= planned_to)
    if master_task_id is not None:
        filters.append(Task.master_task_id == master_task_id)
    if category_id is not None:
        filters.append(MasterTask.category_id == category_id)

    completed = func.count().filter(Task.result == TaskResult.COMPLETED)
    not_completed = func.count().filter(Task.result == TaskResult.NOT_COMPLETED)
    summary_statement = select(
        completed.label("completed_count"),
        not_completed.label("not_completed_count"),
    ).select_from(Task)
    if category_id is not None:
        summary_statement = summary_statement.join(MasterTask)
    summary_row = db.execute(summary_statement.where(*filters)).one()._mapping
    completed_count = int(summary_row["completed_count"])
    not_completed_count = int(summary_row["not_completed_count"])
    terminal_count = completed_count + not_completed_count

    breakdown_statement = (
        select(
            MasterTask.id.label("master_task_id"),
            MasterTask.name.label("master_task_name"),
            Category.id.label("category_id"),
            Category.name.label("category_name"),
            completed.label("completed_count"),
            not_completed.label("not_completed_count"),
        )
        .select_from(Task)
        .join(MasterTask, Task.master_task_id == MasterTask.id)
        .join(Category, MasterTask.category_id == Category.id)
        .where(
            *filters,
            Task.result.in_((TaskResult.COMPLETED, TaskResult.NOT_COMPLETED)),
        )
        .group_by(MasterTask.id, MasterTask.name, Category.id, Category.name)
        .order_by(MasterTask.normalized_name, MasterTask.id)
    )
    rows = db.execute(breakdown_statement).all()
    by_master_task = []
    for row in rows:
        values = row._mapping
        row_completed = int(values["completed_count"])
        row_not_completed = int(values["not_completed_count"])
        row_terminal = row_completed + row_not_completed
        by_master_task.append(
            TaskMasterTaskReportRow(
                master_task_id=values["master_task_id"],
                master_task_name=values["master_task_name"],
                category_id=values["category_id"],
                category_name=values["category_name"],
                completed_count=row_completed,
                not_completed_count=row_not_completed,
                terminal_count=row_terminal,
                completion_rate=_completion_rate(row_completed, row_terminal),
            )
        )
    return TaskReportResponse(
        period=TaskReportPeriod(
            planned_from=planned_from,
            planned_to=planned_to,
        ),
        summary=TaskOutcomeMetrics(
            completed_count=completed_count,
            not_completed_count=not_completed_count,
            terminal_count=terminal_count,
            completion_rate=_completion_rate(completed_count, terminal_count),
        ),
        by_master_task=by_master_task,
    )
