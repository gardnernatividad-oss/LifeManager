import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { queryKeys } from "../../api/queryKeys";
import { listV2Catalog } from "../../api/v2CatalogApi";
import { getV2ReportSummary } from "../../api/v2ReportApi";
import { listWorkspaceMembers } from "../../api/workspaceApi";
import { useAuth } from "../../hooks/useAuth";
import type { V2Category } from "../../types/v2Catalog";
import type { V2ReportFilters } from "../../types/v2Report";
import { formatShortCalendarDate } from "../../utils/localizedDate";
import { shiftDate, workspaceToday } from "../../utils/workspaceDate";

type Period = "LAST_7_DAYS" | "LAST_30_DAYS" | "CUSTOM" | "ALL";

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
  const [period, setPeriod] = useState<Period>("LAST_30_DAYS");
  const [customFrom, setCustomFrom] = useState("");
  const [customUntil, setCustomUntil] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [responsibleId, setResponsibleId] = useState("");
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
  const optionsReady = categories.isSuccess && (!shared || members.isSuccess);
  const report = useQuery({
    queryKey: queryKeys.v2ReportSummary(workspaceId, filters ?? {}),
    queryFn: () => getV2ReportSummary(workspaceId, filters!),
    enabled: Boolean(workspaceId && filters && optionsReady),
  });

  if (!workspace || !user) {
    return <section className="reports-page"><header className="reports-header"><h1>Reportes</h1></header><div className="report-empty"><h2>Selecciona un espacio de trabajo</h2><p>Necesitas un espacio seleccionado para consultar sus reportes.</p></div></section>;
  }

  const retryOptions = () => void Promise.all([
    categories.refetch(),
    ...(shared ? [members.refetch()] : []),
  ]);
  const activeMembers = members.data?.filter((member) => member.status === "ACTIVE") ?? [];
  const metrics = report.data ? [
    ["Tareas", report.data.counts.tasks],
    ["Pendientes", report.data.counts.pending_items],
    ["Proyectos", report.data.counts.projects],
    ["Actividades", report.data.counts.activities],
  ] as const : [];

  return <section className="reports-page">
    <header className="reports-header"><div><p className="eyebrow">{workspace.name}</p><h1>Reportes</h1><p>Consulta un resumen del espacio seleccionado.</p></div></header>
    <nav className="report-tabs" aria-label="Secciones de Reportes"><span aria-current="page">Resumen</span>{["Tareas", "Pendientes", "Proyectos", "Actividades"].map((label) => <button key={label} type="button" disabled title="Disponible en una etapa posterior">{label}</button>)}</nav>
    <section className="report-section" aria-labelledby="report-filters"><h2 id="report-filters">Filtros</h2>
      <div className="report-period-controls">
        <label>Periodo<select value={period} onChange={(event) => setPeriod(event.target.value as Period)}><option value="LAST_7_DAYS">Últimos 7 días</option><option value="LAST_30_DAYS">Últimos 30 días</option><option value="CUSTOM">Personalizado</option><option value="ALL">Todo el historial</option></select></label>
        {period === "CUSTOM" ? <><label>Desde<input type="date" value={customFrom} onChange={(event) => setCustomFrom(event.target.value)} /></label><label>Hasta<input type="date" value={customUntil} onChange={(event) => setCustomUntil(event.target.value)} /></label></> : null}
        <label>Categoría<select value={categoryId} onChange={(event) => setCategoryId(event.target.value)} disabled={!optionsReady}><option value="">Todas</option>{categories.data?.items.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
        {shared ? <label>Responsable<select value={responsibleId} onChange={(event) => setResponsibleId(event.target.value)} disabled={!optionsReady}><option value="">Todas las personas</option>{activeMembers.map((member) => <option key={member.user_id} value={member.user_id}>{member.display_name}</option>)}</select></label> : null}
      </div>
      {!baseFilters ? <p role="alert" className="report-period-help">La fecha Desde no puede ser posterior a Hasta.</p> : null}
      {(categories.isPending || (shared && members.isPending)) ? <p role="status">Cargando filtros…</p> : null}
      {(categories.isError || (shared && members.isError)) ? <div className="report-error" role="alert"><p>No pudimos cargar las opciones de filtros.</p><button className="secondary-button" type="button" onClick={retryOptions}>Reintentar</button></div> : null}
    </section>
    <section className="report-section" aria-labelledby="report-summary"><div className="report-section-heading"><div><h2 id="report-summary">Resumen</h2><p>Conteos del periodo y filtros seleccionados.</p></div>{report.data?.date_from || report.data?.date_until ? <strong>{report.data.date_from ? formatShortCalendarDate(report.data.date_from) : "Inicio"} – {report.data.date_until ? formatShortCalendarDate(report.data.date_until) : "Hoy"}</strong> : <strong>Todo el historial</strong>}</div>
      {report.isPending && optionsReady && filters ? <div className="report-skeleton" role="status" aria-label="Cargando resumen de Reportes" /> : null}
      {report.isError ? <div className="report-error" role="alert"><p>No pudimos cargar el resumen de Reportes.</p><button className="secondary-button" type="button" onClick={() => void report.refetch()}>Reintentar</button></div> : null}
      {report.data && report.data.counts.total === 0 ? <div className="report-empty"><h3>No hay datos para estos filtros</h3><p>Prueba otro periodo, Categoría o Responsable.</p></div> : null}
      {report.data && report.data.counts.total > 0 ? <><div className="report-metric-grid">{metrics.map(([label, value]) => <article className="metric-card" key={label}><span>{label}</span><strong>{value}</strong></article>)}</div><p className="report-total">Total de registros: <strong>{report.data.counts.total}</strong></p></> : null}
    </section>
  </section>;
}
