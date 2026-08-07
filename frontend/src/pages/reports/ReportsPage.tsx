import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { getDashboardStatistics, getDashboardSummary } from "../../api/dashboardApi";
import { queryKeys } from "../../api/queryKeys";
import { getReportTaskCounts } from "../../api/reportApi";
import { useAuth } from "../../hooks/useAuth";
import type { DashboardStatistics, DashboardSummary } from "../../types/dashboard";
import type { ReportPeriod, ReportPeriodBounds, ReportTaskCounts } from "../../types/report";
import { getReportPeriodBounds } from "../../utils/reportPeriod";

const resultMetrics: Array<[keyof DashboardStatistics, string]> = [
  ["completed_tasks", "Completadas"],
  ["not_completed_tasks", "No realizadas"],
  ["cancelled_tasks", "Canceladas"],
  ["resolved_tasks", "Resueltas"],
  ["pending_tasks", "Pendientes"],
  ["scheduled_tasks", "Programadas"]
];

const currentMetrics: Array<[keyof DashboardSummary, string]> = [
  ["total_tasks", "Total"],
  ["overdue_tasks", "Vencidas"],
  ["tasks_due_today", "Para hoy"],
  ["tasks_due_next_7_days", "Próximos 7 días"],
  ["pending_tasks", "Pendientes"],
  ["scheduled_tasks", "Programadas"]
];

function ErrorPanel({ message, retry }: { message: string; retry: () => void }) {
  return <div className="report-error" role="alert"><p>{message}</p><button className="secondary-button" type="button" onClick={retry}>Reintentar</button></div>;
}

function Loading({ label }: { label: string }) {
  return <div className="report-skeleton" role="status" aria-label={label}><span className="sr-only">{label}</span></div>;
}

function periodLabel(bounds: ReportPeriodBounds): string {
  const format = (value: string) => new Intl.DateTimeFormat("es-PE", {
    day: "numeric", month: "short", year: "numeric", timeZone: "UTC"
  }).format(new Date(`${value}T00:00:00Z`));
  return `${format(bounds.fromDate)} – ${format(bounds.toDate)}`;
}

function tasksLink(bounds: ReportPeriodBounds, outcome?: string): string {
  const params = new URLSearchParams({ scheduled_from: bounds.scheduledFrom, scheduled_to: bounds.scheduledTo });
  if (outcome) params.set("outcome", outcome);
  return `/tasks?${params.toString()}`;
}

function PeriodResults({ counts, bounds }: { counts: ReportTaskCounts; bounds: ReportPeriodBounds }) {
  const metrics: Array<[string, number]> = [
    ["Tareas programadas", counts.total],
    ["Completadas", counts.completed],
    ["No realizadas", counts.notCompleted],
    ["Canceladas", counts.cancelled],
    ["Sin resultado terminal", counts.unresolved]
  ];
  return <>
    {counts.total === 0 ? <div className="report-empty"><h3>No hay tareas programadas en este período</h3><p>Prueba otro período o crea una tarea para comenzar.</p><Link className="secondary-button" to="/tasks">Ir a Tareas</Link></div> :
      <div className="report-period-results"><div className="report-metric-grid">{metrics.map(([label, value]) => <article className="metric-card" key={label}><span>{label}</span><strong>{value}</strong></article>)}</div><p className="report-period-help">“Sin resultado terminal” reúne las tareas pendientes y programadas cuyo resultado todavía no es completada, no realizada ni cancelada.</p>
        <nav className="report-links" aria-label="Explorar tareas del período"><Link to={tasksLink(bounds)}>Ver todas las tareas programadas</Link><Link to={tasksLink(bounds, "completed")}>Ver completadas</Link><Link to={tasksLink(bounds, "not_completed")}>Ver no realizadas</Link><Link to={tasksLink(bounds, "cancelled")}>Ver canceladas</Link></nav>
      </div>}
  </>;
}

export function ReportsPage() {
  const { workspace } = useAuth();
  const workspaceId = workspace?.id ?? "";
  const [period, setPeriod] = useState<ReportPeriod>("this_month");
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");
  const bounds = useMemo(() => workspace ? getReportPeriodBounds(period, workspace.timezone, customFrom, customTo) : null, [period, workspace, customFrom, customTo]);
  const summaryQuery = useQuery({ queryKey: queryKeys.dashboardSummary(workspaceId), queryFn: () => getDashboardSummary(workspaceId), enabled: Boolean(workspaceId), staleTime: 30_000 });
  const statisticsQuery = useQuery({ queryKey: queryKeys.dashboardStatistics(workspaceId), queryFn: () => getDashboardStatistics(workspaceId), enabled: Boolean(workspaceId), staleTime: 30_000 });
  const countsQuery = useQuery({
    queryKey: queryKeys.reportTaskCounts(workspaceId, bounds?.scheduledFrom ?? "", bounds?.scheduledTo ?? ""),
    queryFn: () => getReportTaskCounts(workspaceId, bounds!.scheduledFrom, bounds!.scheduledTo),
    enabled: Boolean(workspaceId && bounds),
    staleTime: 30_000
  });

  if (!workspace) return <div className="reports-page"><header className="reports-header"><p className="eyebrow">LifeManager</p><h1>Reportes</h1></header><section className="report-empty"><h2>Selecciona un espacio de trabajo</h2><p>Necesitas un espacio seleccionado para consultar sus resultados.</p></section></div>;
  const refreshing = summaryQuery.isFetching || statisticsQuery.isFetching || countsQuery.isFetching;
  const refresh = () => void Promise.all([summaryQuery.refetch(), statisticsQuery.refetch(), ...(bounds ? [countsQuery.refetch()] : [])]);

  return <div className="reports-page">
    <header className="reports-header"><div><p className="eyebrow">{workspace.name}</p><h1>Reportes</h1><p>Consulta resultados reales y el estado de las tareas del espacio seleccionado.</p></div><button className="secondary-button" type="button" disabled={refreshing} onClick={refresh}>{refreshing ? "Actualizando…" : "Actualizar reportes"}</button></header>

    <section className="report-section" aria-labelledby="compliance-title"><h2 id="compliance-title">Resumen de cumplimiento</h2><p>La tasa corresponde a tareas completadas sobre todas las tareas resueltas del espacio.</p>
      {statisticsQuery.isPending && <Loading label="Cargando resumen de cumplimiento" />}
      {statisticsQuery.isError && <ErrorPanel message="No pudimos cargar el resumen de cumplimiento." retry={() => void statisticsQuery.refetch()} />}
      {statisticsQuery.data && <div className="report-completion"><div className="completion-rate"><span>Tasa de cumplimiento</span><strong>{statisticsQuery.data.completion_rate.toFixed(2)}%</strong><div className="progress-track" role="progressbar" aria-label="Tasa de cumplimiento" aria-valuemin={0} aria-valuemax={100} aria-valuenow={statisticsQuery.data.completion_rate}><span style={{ width: `${statisticsQuery.data.completion_rate}%` }} /></div></div><dl className="statistics-grid">{resultMetrics.map(([field, label]) => <div key={field}><dt>{label}</dt><dd>{statisticsQuery.data[field]}</dd></div>)}</dl></div>}
    </section>

    <section className="report-section" aria-labelledby="current-title"><h2 id="current-title">Estado actual</h2><p>Una vista operativa de las tareas que requieren atención ahora.</p>
      {summaryQuery.isPending && <Loading label="Cargando estado actual" />}
      {summaryQuery.isError && <ErrorPanel message="No pudimos cargar el estado actual de las tareas." retry={() => void summaryQuery.refetch()} />}
      {summaryQuery.data && (summaryQuery.data.total_tasks === 0 ? <div className="report-empty"><h3>Este espacio todavía no tiene tareas</h3><p>Crea una tarea para empezar a construir tu reporte.</p><Link className="secondary-button" to="/tasks">Crear o administrar tareas</Link></div> : <div className="report-metric-grid">{currentMetrics.map(([field, label]) => <article className="metric-card" key={field}><span>{label}</span><strong>{summaryQuery.data[field]}</strong></article>)}</div>)}
    </section>

    <section className="report-section" aria-labelledby="period-title"><div className="report-section-heading"><div><h2 id="period-title">Tareas programadas por período</h2><p>Los resultados se filtran por la fecha programada de la tarea, no por su fecha de resolución.</p></div>{bounds && <strong>{periodLabel(bounds)}</strong>}</div>
      <div className="report-period-controls"><label htmlFor="report-period">Período<select id="report-period" value={period} onChange={(event) => setPeriod(event.target.value as ReportPeriod)}><option value="this_week">Esta semana</option><option value="this_month">Este mes</option><option value="last_30_days">Últimos 30 días</option><option value="custom">Personalizado</option></select></label>{period === "custom" && <><label htmlFor="report-from">Desde<input id="report-from" type="date" value={customFrom} onChange={(event) => setCustomFrom(event.target.value)} /></label><label htmlFor="report-to">Hasta<input id="report-to" type="date" value={customTo} min={customFrom || undefined} onChange={(event) => setCustomTo(event.target.value)} /></label></>}</div>
      {period === "custom" && !bounds && <p className="report-period-help" role="status">Selecciona un rango válido para consultar las tareas programadas.</p>}
      {bounds && countsQuery.isPending && <Loading label="Cargando tareas programadas del período" />}
      {bounds && countsQuery.isError && <ErrorPanel message="No pudimos cargar las tareas programadas del período." retry={() => void countsQuery.refetch()} />}
      {bounds && countsQuery.data && <PeriodResults counts={countsQuery.data} bounds={bounds} />}
    </section>
  </div>;
}
