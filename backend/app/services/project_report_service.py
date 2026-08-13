import uuid

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.models import Category, Project, ProjectStep
from app.schemas.project import ProjectState, StepCompliance
from app.schemas.project_report import (
    ProjectReportFilters,
    ProjectReportPeriod,
    ProjectReportResponse,
    ProjectReportRow,
    ProjectReportSummary,
    ProjectStepComplianceSummary,
    ProjectStepDetailSummary,
)


class ProjectReportCategoryNotFoundError(LookupError):
    pass


def _project_metrics(workspace_id: uuid.UUID):
    valid_step = and_(
        ProjectStep.planned_date.is_not(None),
        ProjectStep.weight.is_not(None),
        ProjectStep.weight > 0,
    )
    aggregate = (
        select(
            Project.id.label("project_id"),
            Project.name.label("project_name"),
            Project.category_id.label("category_id"),
            Category.name.label("category_name"),
            Project.is_active.label("is_active"),
            func.count(ProjectStep.id).label("step_count"),
            func.count(ProjectStep.id).filter(valid_step).label("valid_step_count"),
            func.coalesce(func.sum(ProjectStep.weight), 0).label("total_weight"),
            func.max(ProjectStep.planned_date).label("planned_date"),
            func.min(ProjectStep.progress).label("minimum_progress"),
            func.max(ProjectStep.progress).label("maximum_progress"),
            func.coalesce(
                func.sum(ProjectStep.weight * ProjectStep.progress), 0
            ).label("weighted_progress_sum"),
        )
        .select_from(Project)
        .join(Category, Project.category_id == Category.id)
        .outerjoin(ProjectStep, ProjectStep.project_id == Project.id)
        .where(Project.workspace_id == workspace_id)
        .group_by(
            Project.id,
            Project.name,
            Project.category_id,
            Category.name,
            Project.is_active,
        )
        .cte("project_report_aggregate")
    )
    complete = and_(
        aggregate.c.step_count > 0,
        aggregate.c.valid_step_count == aggregate.c.step_count,
        aggregate.c.total_weight == Decimal("100.00"),
    )
    return select(
        aggregate.c.project_id,
        aggregate.c.project_name,
        aggregate.c.category_id,
        aggregate.c.category_name,
        aggregate.c.is_active,
        aggregate.c.step_count,
        aggregate.c.planned_date,
        case(
            (complete, aggregate.c.weighted_progress_sum / Decimal("100.00")),
            else_=None,
        ).label("progress"),
        case(
            (complete & (aggregate.c.maximum_progress == 0), ProjectState.NO_INICIADO.value),
            (complete & (aggregate.c.minimum_progress == 100), ProjectState.FINALIZADO.value),
            (complete, ProjectState.EN_PROCESO.value),
            else_=None,
        ).label("state"),
    ).cte("project_report_metrics")


def _population(projects, *, planned_from, planned_to, category_id, is_active, state):
    filters = []
    if planned_from is not None:
        filters.append(projects.c.planned_date >= planned_from)
    if planned_to is not None:
        filters.append(projects.c.planned_date <= planned_to)
    if category_id is not None:
        filters.append(projects.c.category_id == category_id)
    if is_active is not None:
        filters.append(projects.c.is_active == is_active)
    if state is not None:
        filters.append(projects.c.state == state.value)
    return select(projects).where(*filters).cte("project_report_population")


def _step_compliance_predicates(local_date: date):
    has_planned_date = ProjectStep.planned_date.is_not(None)
    return {
        StepCompliance.EN_PLAZO: (
            has_planned_date
            & ProjectStep.completion_date.is_(None)
            & (ProjectStep.planned_date >= local_date)
        ),
        StepCompliance.ATRASADO: (
            has_planned_date
            & ProjectStep.completion_date.is_(None)
            & (ProjectStep.planned_date < local_date)
        ),
        StepCompliance.CON_ADELANTO: (
            has_planned_date
            & (ProjectStep.completion_date < ProjectStep.planned_date)
        ),
        StepCompliance.A_TIEMPO: (
            has_planned_date
            & (ProjectStep.completion_date == ProjectStep.planned_date)
        ),
        StepCompliance.CON_RETRASO: (
            has_planned_date
            & (ProjectStep.completion_date > ProjectStep.planned_date)
        ),
    }


def _summary(values) -> ProjectReportSummary:
    return ProjectReportSummary(
        **{
            name: int(values[name])
            for name in (
                "total_count",
                "active_count",
                "inactive_count",
                "no_iniciado_count",
                "en_proceso_count",
                "finalizado_count",
            )
        }
    )


def _average(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_project_report(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    local_date: date,
    planned_from: date | None = None,
    planned_to: date | None = None,
    category_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    state: ProjectState | None = None,
) -> ProjectReportResponse:
    if category_id is not None:
        category_exists = db.scalar(
            select(Category.id).where(
                Category.id == category_id,
                Category.workspace_id == workspace_id,
            )
        )
        if category_exists is None:
            raise ProjectReportCategoryNotFoundError("Category not found")

    projects = _project_metrics(workspace_id)
    population = _population(
        projects,
        planned_from=planned_from,
        planned_to=planned_to,
        category_id=category_id,
        is_active=is_active,
        state=state,
    )
    summary_values = db.execute(
        select(
            func.count().label("total_count"),
            func.count().filter(population.c.is_active.is_(True)).label("active_count"),
            func.count().filter(population.c.is_active.is_(False)).label("inactive_count"),
            func.count().filter(population.c.state == ProjectState.NO_INICIADO.value).label("no_iniciado_count"),
            func.count().filter(population.c.state == ProjectState.EN_PROCESO.value).label("en_proceso_count"),
            func.count().filter(population.c.state == ProjectState.FINALIZADO.value).label("finalizado_count"),
        ).select_from(population)
    ).one()._mapping
    project_rows = db.execute(
        select(population).order_by(
            population.c.planned_date.asc().nulls_last(),
            population.c.project_name,
            population.c.project_id,
        )
    ).all()

    compliance = _step_compliance_predicates(local_date)
    step_values = db.execute(
        select(
            func.count().filter(compliance[StepCompliance.EN_PLAZO]).label("en_plazo_count"),
            func.count().filter(compliance[StepCompliance.ATRASADO]).label("atrasado_count"),
            func.count().filter(compliance[StepCompliance.CON_ADELANTO]).label("con_adelanto_count"),
            func.count().filter(compliance[StepCompliance.A_TIEMPO]).label("a_tiempo_count"),
            func.count().filter(compliance[StepCompliance.CON_RETRASO]).label("con_retraso_count"),
            func.avg(
                case(
                    (compliance[StepCompliance.ATRASADO], local_date - ProjectStep.planned_date),
                    else_=None,
                )
            ).label("average_atrasado_days"),
            func.avg(
                case(
                    (
                        compliance[StepCompliance.CON_ADELANTO],
                        ProjectStep.planned_date - ProjectStep.completion_date,
                    ),
                    else_=None,
                )
            ).label("average_con_adelanto_days"),
            func.avg(
                case(
                    (
                        compliance[StepCompliance.CON_RETRASO],
                        ProjectStep.completion_date - ProjectStep.planned_date,
                    ),
                    else_=None,
                )
            ).label("average_con_retraso_days"),
        )
        .select_from(ProjectStep)
        .join(population, ProjectStep.project_id == population.c.project_id)
    ).one()._mapping

    return ProjectReportResponse(
        period=ProjectReportPeriod(planned_from=planned_from, planned_to=planned_to),
        filters=ProjectReportFilters(
            category_id=category_id,
            is_active=is_active,
            state=state,
        ),
        summary=_summary(summary_values),
        step_compliance=ProjectStepComplianceSummary(
            **{
                name: int(step_values[name])
                for name in (
                    "en_plazo_count",
                    "atrasado_count",
                    "con_adelanto_count",
                    "a_tiempo_count",
                    "con_retraso_count",
                )
            }
        ),
        detail=ProjectStepDetailSummary(
            average_atrasado_days=_average(step_values["average_atrasado_days"]),
            average_con_adelanto_days=_average(step_values["average_con_adelanto_days"]),
            average_con_retraso_days=_average(step_values["average_con_retraso_days"]),
        ),
        by_project=[
            ProjectReportRow(
                project_id=row._mapping["project_id"],
                project_name=row._mapping["project_name"],
                category_id=row._mapping["category_id"],
                category_name=row._mapping["category_name"],
                is_active=row._mapping["is_active"],
                planned_date=row._mapping["planned_date"],
                progress=row._mapping["progress"],
                state=row._mapping["state"],
                step_count=int(row._mapping["step_count"]),
            )
            for row in project_rows
        ],
    )
