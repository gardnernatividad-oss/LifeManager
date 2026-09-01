import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { queryKeys } from "../../api/queryKeys";
import { listV2Catalog } from "../../api/v2CatalogApi";
import { getV2ActivityReport, getV2PendingReport, getV2ProjectReport, getV2ReportSummary, getV2TaskReport } from "../../api/v2ReportApi";
import { listWorkspaceMembers } from "../../api/workspaceApi";
import { useAuth } from "../../hooks/useAuth";
import type { V2CatalogItem, V2Category } from "../../types/v2Catalog";
import type { ActivityReportGroup, ComplianceMetrics, ProgressCategoryGroup, ProgressEvolution, ProgressReportMetrics, TaskReportEvolution, TaskReportGroup, V2ReportFilters } from "../../types/v2Report";
import { formatShortCalendarDate } from "../../utils/localizedDate";
import { shiftDate, workspaceToday } from "../../utils/workspaceDate";

type Period = "LAST_7_DAYS" | "LAST_30_DAYS" | "CUSTOM" | "ALL";
type Section = "summary" | "tasks" | "pending-items" | "projects" | "activities";

function ActivityBreakdown({ title, rows }: { title: string; rows: ActivityReportGroup[] }) {
  return <><h3>{title}</h3><div className="report-table-wrap"><table><thead><tr><th>{title.replace("Por ", "")}</th><th>Cantidad</th><th>Duración total</th><th>Duración promedio</th></tr></thead><tbody>{rows.map((row) => <tr key={row.key}><td>{row.label}</td><td>{row.total_count}</td><td>{row.total_duration_minutes} min</td><td>{row.average_duration_minutes === null ? "—" : `${row.average_duration_minutes} min`}</td></tr>)}</tbody></table></div></>;
}

function ProgressMetrics({ values }: { values: ProgressReportMetrics }) {
  return <div className="report-metric-grid"><article className="metric-card"><span>Total</span><strong>{values.total_count}</strong></article><article className="metric-card"><span>No iniciados</span><strong>{values.no_iniciado_count}</strong></article><article className="metric-card"><span>En proceso</span><strong>{values.en_proceso_count}</strong></article><article className="metric-card"><span>Finalizados</span><strong>{values.finalizado_count}</strong></article>{values.configuracion_incompleta_count ? <article className="metric-card"><span>Configuración incompleta</span><strong>{values.configuracion_incompleta_count}</strong></article> : null}<article className="metric-card"><span>Avance promedio</span><strong>{values.average_progress === null ? "—" : `${values.average_progress}%`}</strong></article></div>;
}

function Compliance({ values, title = "Cumplimiento" }: { values: ComplianceMetrics; title?: string }) {
  return <div><h3>{title}</h3><dl className="statistics-grid"><div><dt>En plazo</dt><dd>{values.en_plazo_count}</dd></div><div><dt>Atrasados</dt><dd>{values.atrasado_count}</dd></div><div><dt>Con adelanto</dt><dd>{values.con_adelanto_count}</dd></div><div><dt>A tiempo</dt><dd>{values.a_tiempo_count}</dd></div><div><dt>Con retraso</dt><dd>{values.con_retraso_count}</dd></div></dl></div>;
}

function ProgressBreakdowns({ categories, evolution }: { categories: ProgressCategoryGroup[]; evolution: ProgressEvolution[] }) {
  return <><h3>Por Categoría</h3><div className="report-table-wrap"><table><thead><tr><th>Categoría</th><th>Total</th><th>Avance promedio</th></tr></thead><tbody>{categories.map((row) => <tr key={row.category_id}><td>{row.category_name}</td><td>{row.total_count}</td><td>{row.average_progress === null ? "—" : `${row.average_progress}%`}</td></tr>)}</tbody></table></div><h3>Evolución por fecha planificada</h3><div className="report-table-wrap"><table><thead><tr><th>Fecha</th><th>Total</th><th>Avance promedio</th></tr></thead><tbody>{evolution.map((row) => <tr key={row.planned_date}><td>{formatShortCalendarDate(row.planned_date)}</td><td>{row.total_count}</td><td>{row.average_progress === null ? "—" : `${row.average_progress}%`}</td></tr>)}</tbody></table></div></>;
}

function TaskBreakdown({ title, rows }: { title: string; rows: TaskReportGroup[] }) {
  return <><h3>{title}</h3><div className="report-table-wrap"><table><thead><tr><th>{title === "Por Tarea" ? "Tarea" : "Categoría"}</th><th>Total</th><th>Completadas</th><th>No realizadas</th><th>Cumplimiento</th></tr></thead><tbody>{rows.map((row) => <tr key={row.key}><td>{row.label}</td><td>{row.total_count}</td><td>{row.completed_count}</td><td>{row.not_completed_count}</td><td>{row.completion_rate === null ? "—" : `${row.completion_rate}%`}</td></tr>)}</tbody></table></div></>;
}

function TaskEvolutionTable({ rows }: { rows: TaskReportEvolution[] }) {
  return <><h3>Evolución por fecha planificada</h3><div className="report-table-wrap"><table><thead><tr><th>Fecha</th><th>Pendientes</th><th>Completadas</th><th>No realizadas</th></tr></thead><tbody>{rows.map((row) => <tr key={row.planned_date}><td>{formatShortCalendarDate(row.planned_date)}</td><td>{row.pending_count}</td><td>{row.completed_count}</td><td>{row.not_completed_count}</td></tr>)}</tbody></table></div></>;
}

function periodFilters(
  period: Period,
  timeZone: string,
  customFrom: string,
  customUntil: string,
): V2ReportFilters | null {
  if (period === "ALL") return {};
  if (period === "CUSTOM") {
    if (customFrom && customUntil && customFrom > customUntil) return null;
    return {
      ...(customFrom ? { date_from: customFrom } : {}),
      ...(customUntil ? { date_until: customUntil } : {}),
    };
  }
  const today = workspaceToday(timeZone);
  return {
    date_from: shiftDate(today, period === "LAST_7_DAYS" ? -6 : -29),
    date_until: today,
  };
}

export function ReportsPage() {
  const { workspace, user } = useAuth();
  const workspaceId = workspace?.id ?? "";
  const shared = workspace?.kind === "SHARED";
  const [section, setSection] = useState<Section>("summary");
  const [period, setPeriod] = useState<Period>("LAST_30_DAYS");
  const [customFrom, setCustomFrom] = useState("");
  const [customUntil, setCustomUntil] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [responsibleId, setResponsibleId] = useState("");
  const [taskSource, setTaskSource] = useState("");
  const [activitySource, setActivitySource] = useState("");
  const baseFilters = useMemo(
    () => workspace ? periodFilters(period, workspace.timezone, customFrom, customUntil) : null,
    [period, workspace, customFrom, customUntil],
  );
  const filters = useMemo<V2ReportFilters | null>(
    () => baseFilters && ({
      ...baseFilters,
      ...(categoryId ? { category_id: categoryId } : {}),
      ...(responsibleId ? { responsible_user_id: responsibleId } : {}),
    }),
    [baseFilters, categoryId, responsibleId],
  );
  const categories = useQuery({
    queryKey: queryKeys.v2Catalog(workspaceId, "categories", { report: true }),
    queryFn: () => listV2Catalog<V2Category>(workspaceId, "categories", {}),
    enabled: Boolean(workspaceId),
  });
  const members = useQuery({
    queryKey: queryKeys.workspaceMembers(workspaceId),
    queryFn: () => listWorkspaceMembers(workspaceId),
    enabled: Boolean(workspaceId && shared),
  });
  const masters = useQuery({ queryKey: queryKeys.v2Catalog(workspaceId, "master-tasks", { report: true }), queryFn: () => listV2Catalog<V2CatalogItem>(workspaceId, "master-tasks", {}), enabled: Boolean(workspaceId && section === "tasks") });
  const activityMasters = useQuery({ queryKey: queryKeys.v2Catalog(workspaceId, "activity-masters", { report: true }), queryFn: () => listV2Catalog<V2CatalogItem>(workspaceId, "activity-masters", {}), enabled: Boolean(workspaceId && section === "activities") });
  const optionsReady = categories.isSuccess && (!shared || members.isSuccess) && (section !== "tasks" || masters.isSuccess) && (section !== "activities" || activityMasters.isSuccess);
  const report = useQuery({
    queryKey: queryKeys.v2ReportSummary(workspaceId, filters ?? {}),
    queryFn: () => getV2ReportSummary(workspaceId, filters!),
    enabled: Boolean(workspaceId && filters && optionsReady && section === "summary"),
  });
  const taskFilters = useMemo(() => ({ ...(filters ?? {}), ...(taskSource === "CUSTOM" ? { custom_tasks: true } : taskSource ? { master_task_id: taskSource } : {}) }), [filters, taskSource]);
  const tasksReport = useQuery({ queryKey: queryKeys.v2ReportDetail(workspaceId, "tasks", taskFilters), queryFn: () => getV2TaskReport(workspaceId, taskFilters), enabled: Boolean(workspaceId && filters && optionsReady && section === "tasks") });
  const pendingReport = useQuery({ queryKey: queryKeys.v2ReportDetail(workspaceId, "pending-items", filters ?? {}), queryFn: () => getV2PendingReport(workspaceId, filters!), enabled: Boolean(workspaceId && filters && optionsReady && section === "pending-items") });
  const projectReport = useQuery({ queryKey: queryKeys.v2ReportDetail(workspaceId, "projects", filters ?? {}), queryFn: () => getV2ProjectReport(workspaceId, filters!), enabled: Boolean(workspaceId && filters && optionsReady && section === "projects") });
  const activityFilters = useMemo(() => ({ ...(filters ?? {}), ...(activitySource === "CUSTOM" ? { custom_activities: true } : activitySource ? { activity_master_id: activitySource } : {}) }), [filters, activitySource]);
  const activityReport = useQuery({ queryKey: queryKeys.v2ReportDetail(workspaceId, "activities", activityFilters), queryFn: () => getV2ActivityReport(workspaceId, activityFilters), enabled: Boolean(workspaceId && filters && optionsReady && section === "activities") });

  if (!workspace || !user) {
    return <section className="reports-page"><header className="reports-header"><h1>Reportes</h1></header><div className="report-empty"><h2>Selecciona un espacio de trabajo</h2><p>Necesitas un espacio seleccionado para consultar sus reportes.</p></div></section>;
  }

  const retryOptions = () => void Promise.all([
    categories.refetch(),
    ...(shared ? [members.refetch()] : []),
    ...(section === "tasks" ? [masters.refetch()] : []),
    ...(section === "activities" ? [activityMasters.refetch()] : []),
  ]);
  const activeMembers = shared
    ? members.data?.filter((member) => member.status === "ACTIVE") ?? []
    : [{ user_id: user.id, display_name: `${user.first_name} ${user.last_name}`, email: user.email }];
  const personFilterLabel = section === "projects" ? "Líder" : section === "activities" ? "Organizador" : "Responsable";
  const metrics = report.data ? [
    ["Tareas", report.data.counts.tasks],
    ["Pendientes", report.data.counts.pending_items],
    ["Proyectos", report.data.counts.projects],
    ["Actividades", report.data.counts.activities],
  ] as const : [];

  return <section className="reports-page">
    <header className="reports-header"><div><p className="eyebrow">{workspace.name}</p><h1>Reportes</h1><p>Consulta un resumen del espacio seleccionado.</p></div></header>
    <nav className="report-tabs" aria-label="Secciones de Reportes">{[["summary", "Resumen"], ["tasks", "Tareas"], ["pending-items", "Pendientes"], ["projects", "Proyectos"], ["activities", "Actividades"]].map(([value, label]) => <button key={value} type="button" aria-current={section === value ? "page" : undefined} onClick={() => setSection(value as Section)}>{label}</button>)}</nav>
    <section className="report-section" aria-labelledby="report-filters"><h2 id="report-filters">Filtros</h2>
      <div className="report-period-controls">
        <label>Periodo<select value={period} onChange={(event) => setPeriod(event.target.value as Period)}><option value="LAST_7_DAYS">Últimos 7 días</option><option value="LAST_30_DAYS">Últimos 30 días</option><option value="CUSTOM">Personalizado</option><option value="ALL">Todo el historial</option></select></label>
        {period === "CUSTOM" ? <><label>Desde<input type="date" value={customFrom} onChange={(event) => setCustomFrom(event.target.value)} /></label><label>Hasta<input type="date" value={customUntil} onChange={(event) => setCustomUntil(event.target.value)} /></label></> : null}
        <label>Categoría<select value={categoryId} onChange={(event) => setCategoryId(event.target.value)} disabled={!optionsReady}><option value="">Todas</option>{categories.data?.items.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
        <label>{personFilterLabel}<select value={responsibleId} onChange={(event) => setResponsibleId(event.target.value)} disabled={!optionsReady}><option value="">Todas las personas</option>{activeMembers.map((member) => <option key={member.user_id} value={member.user_id}>{member.display_name}</option>)}</select></label>
        {section === "tasks" ? <label>Tarea<select value={taskSource} onChange={(event) => setTaskSource(event.target.value)} disabled={!optionsReady}><option value="">Todas</option>{masters.data?.items.map((master) => <option key={master.id} value={master.id}>{master.name}</option>)}<option value="CUSTOM">Otras tareas</option></select></label> : null}
        {section === "activities" ? <label>Actividad<select value={activitySource} onChange={(event) => setActivitySource(event.target.value)} disabled={!optionsReady}><option value="">Todas</option>{activityMasters.data?.items.map((master) => <option key={master.id} value={master.id}>{master.name}</option>)}<option value="CUSTOM">Otras actividades</option></select></label> : null}
      </div>
      {!baseFilters ? <p role="alert" className="report-period-help">La fecha Desde no puede ser posterior a Hasta.</p> : null}
      {(categories.isPending || (shared && members.isPending) || (section === "tasks" && masters.isPending) || (section === "activities" && activityMasters.isPending)) ? <p role="status">Cargando filtros…</p> : null}
      {(categories.isError || (shared && members.isError) || (section === "tasks" && masters.isError) || (section === "activities" && activityMasters.isError)) ? <div className="report-error" role="alert"><p>No pudimos cargar las opciones de filtros.</p><button className="secondary-button" type="button" onClick={retryOptions}>Reintentar</button></div> : null}
    </section>
    {section === "summary" ? <section className="report-section" aria-labelledby="report-summary"><div className="report-section-heading"><div><h2 id="report-summary">Resumen</h2><p>Conteos del periodo y filtros seleccionados.</p></div>{report.data?.date_from || report.data?.date_until ? <strong>{report.data.date_from ? formatShortCalendarDate(report.data.date_from) : "Inicio"} – {report.data.date_until ? formatShortCalendarDate(report.data.date_until) : "Hoy"}</strong> : <strong>Todo el historial</strong>}</div>
      {report.isPending && optionsReady && filters ? <div className="report-skeleton" role="status" aria-label="Cargando resumen de Reportes" /> : null}
      {report.isError ? <div className="report-error" role="alert"><p>No pudimos cargar el resumen de Reportes.</p><button className="secondary-button" type="button" onClick={() => void report.refetch()}>Reintentar</button></div> : null}
      {report.data && report.data.counts.total === 0 ? <div className="report-empty"><h3>No hay datos para estos filtros</h3><p>Prueba otro periodo, Categoría o Responsable.</p></div> : null}
      {report.data && report.data.counts.total > 0 ? <><div className="report-metric-grid">{metrics.map(([label, value]) => <article className="metric-card" key={label}><span>{label}</span><strong>{value}</strong></article>)}</div><p className="report-total">Total de registros: <strong>{report.data.counts.total}</strong></p></> : null}
    </section> : null}
    {section === "tasks" ? <section className="report-section"><h2>Resultados de Tareas</h2>{tasksReport.isPending && optionsReady ? <div className="report-skeleton" role="status" aria-label="Cargando reporte de Tareas" /> : null}{tasksReport.isError ? <div className="report-error" role="alert"><p>No pudimos cargar el reporte de Tareas.</p><button type="button" onClick={() => void tasksReport.refetch()}>Reintentar</button></div> : null}{tasksReport.data?.summary.total_count === 0 ? <div className="report-empty"><h3>No hay Tareas para estos filtros</h3></div> : null}{tasksReport.data && tasksReport.data.summary.total_count > 0 ? <><div className="report-metric-grid"><article className="metric-card"><span>Total</span><strong>{tasksReport.data.summary.total_count}</strong></article><article className="metric-card"><span>Pendientes</span><strong>{tasksReport.data.summary.pending_count}</strong></article><article className="metric-card"><span>Completadas</span><strong>{tasksReport.data.summary.completed_count}</strong></article><article className="metric-card"><span>No realizadas</span><strong>{tasksReport.data.summary.not_completed_count}</strong></article><article className="metric-card"><span>Cumplimiento</span><strong>{tasksReport.data.summary.completion_rate === null ? "—" : `${tasksReport.data.summary.completion_rate}%`}</strong></article></div><TaskBreakdown title="Por Tarea" rows={tasksReport.data.by_task} /><TaskBreakdown title="Por Categoría" rows={tasksReport.data.by_category} /><TaskEvolutionTable rows={tasksReport.data.evolution} /></> : null}</section> : null}
    {section === "pending-items" ? <section className="report-section"><h2>Avance de Pendientes</h2>{pendingReport.isPending && optionsReady ? <div className="report-skeleton" role="status" aria-label="Cargando reporte de Pendientes" /> : null}{pendingReport.isError ? <div className="report-error" role="alert"><p>No pudimos cargar el reporte de Pendientes.</p><button type="button" onClick={() => void pendingReport.refetch()}>Reintentar</button></div> : null}{pendingReport.data?.summary.total_count === 0 ? <div className="report-empty"><h3>No hay Pendientes para estos filtros</h3></div> : null}{pendingReport.data && pendingReport.data.summary.total_count > 0 ? <><ProgressMetrics values={pendingReport.data.summary} /><Compliance values={pendingReport.data.compliance} /><ProgressBreakdowns categories={pendingReport.data.by_category} evolution={pendingReport.data.evolution} /></> : null}</section> : null}
    {section === "projects" ? <section className="report-section"><h2>Proyectos y Etapas</h2>{projectReport.isPending && optionsReady ? <div className="report-skeleton" role="status" aria-label="Cargando reporte de Proyectos" /> : null}{projectReport.isError ? <div className="report-error" role="alert"><p>No pudimos cargar el reporte de Proyectos.</p><button type="button" onClick={() => void projectReport.refetch()}>Reintentar</button></div> : null}{projectReport.data?.summary.total_count === 0 ? <div className="report-empty"><h3>No hay Proyectos para estos filtros</h3></div> : null}{projectReport.data && projectReport.data.summary.total_count > 0 ? <><ProgressMetrics values={projectReport.data.summary} /><Compliance values={projectReport.data.stage_compliance} title="Cumplimiento de Etapas" /><ProgressBreakdowns categories={projectReport.data.by_category} evolution={projectReport.data.evolution} /><div className="report-table-wrap"><table><thead><tr><th>Proyecto</th><th>Categoría</th><th>Fecha planificada</th><th>Avance</th><th>Estado</th></tr></thead><tbody>{projectReport.data.by_project.map((row) => <tr key={row.project_id}><td>{row.project_name}</td><td>{row.category_name}</td><td>{row.planned_date ? formatShortCalendarDate(row.planned_date) : "—"}</td><td>{row.progress === null ? "—" : `${row.progress}%`}</td><td>{row.state}</td></tr>)}</tbody></table></div></> : null}</section> : null}
    {section === "activities" ? <section className="report-section"><h2>Actividades</h2><p>Cantidad y duración de ocurrencias persistidas.</p>{activityReport.isPending && optionsReady ? <div className="report-skeleton" role="status" aria-label="Cargando reporte de Actividades" /> : null}{activityReport.isError ? <div className="report-error" role="alert"><p>No pudimos cargar el reporte de Actividades.</p><button type="button" onClick={() => void activityReport.refetch()}>Reintentar</button></div> : null}{activityReport.data?.summary.total_count === 0 ? <div className="report-empty"><h3>No hay Actividades para estos filtros</h3></div> : null}{activityReport.data && activityReport.data.summary.total_count > 0 ? <><div className="report-metric-grid"><article className="metric-card"><span>Total</span><strong>{activityReport.data.summary.total_count}</strong></article><article className="metric-card"><span>Programadas</span><strong>{activityReport.data.summary.scheduled_count}</strong></article><article className="metric-card"><span>Canceladas</span><strong>{activityReport.data.summary.cancelled_count}</strong></article><article className="metric-card"><span>Duración total</span><strong>{activityReport.data.summary.total_duration_minutes} min</strong></article><article className="metric-card"><span>Duración promedio</span><strong>{activityReport.data.summary.average_duration_minutes === null ? "—" : `${activityReport.data.summary.average_duration_minutes} min`}</strong></article></div><ActivityBreakdown title="Por Actividad" rows={activityReport.data.by_activity} /><ActivityBreakdown title="Por Categoría" rows={activityReport.data.by_category} /><ActivityBreakdown title="Por Organizador" rows={activityReport.data.by_organizer} /><h3>Evolución por fecha local</h3><div className="report-table-wrap"><table><thead><tr><th>Fecha</th><th>Cantidad</th><th>Duración total</th></tr></thead><tbody>{activityReport.data.evolution.map((row) => <tr key={row.local_date}><td>{formatShortCalendarDate(row.local_date)}</td><td>{row.total_count}</td><td>{row.total_duration_minutes} min</td></tr>)}</tbody></table></div></> : null}</section> : null}
  </section>;
}
