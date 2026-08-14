import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { listAllCategoryOptions } from "../../api/planningPendingItemApi";
import { getProjectReport } from "../../api/projectReportApi";
import { queryKeys } from "../../api/queryKeys";
import type { ProjectReportParams, ProjectReportState } from "../../types/projectReport";
import { formatShortCalendarDate } from "../../utils/localizedDate";

const metric = (value: string | number | null) =>
  value === null ? "—" : Number(value).toFixed(2);
const progress = (value: string | number | null) =>
  value === null ? "—" : `${Number(value).toFixed(2)} %`;
const stateLabels: Record<ProjectReportState, string> = {
  NO_INICIADO: "No iniciado",
  EN_PROCESO: "En proceso",
  FINALIZADO: "Finalizado",
};

export function ProjectReportsPage() {
  const [params, setParams] = useState<ProjectReportParams>({});
  const invalidPeriod = Boolean(
    params.planned_from && params.planned_to && params.planned_from > params.planned_to,
  );
  const categories = useQuery({
    queryKey: queryKeys.categoryOptions,
    queryFn: listAllCategoryOptions,
  });
  const report = useQuery({
    queryKey: queryKeys.projectReports(params),
    queryFn: () => getProjectReport(params),
    enabled: !invalidPeriod && categories.isSuccess,
  });

  return (
    <section className="project-report-page">
      <header><p className="eyebrow">Reportes</p><h1>Reportes · Proyectos</h1></header>

      <section className="task-report-panel">
        <h2>Filtros</h2>
        {categories.isPending ? (
          <p role="status">Cargando categorías…</p>
        ) : categories.isError ? (
          <div role="alert">
            <p>No pudimos cargar las categorías.</p>
            <button onClick={() => void categories.refetch()}>Reintentar</button>
          </div>
        ) : (
          <div className="project-report-filters">
            <label>Desde<input type="date" value={params.planned_from ?? ""} onChange={(event) => setParams({ ...params, planned_from: event.target.value || undefined })} /></label>
            <label>Hasta<input type="date" value={params.planned_to ?? ""} onChange={(event) => setParams({ ...params, planned_to: event.target.value || undefined })} /></label>
            <label>Categoría<select value={params.category_id ?? ""} onChange={(event) => setParams({ ...params, category_id: event.target.value || undefined })}><option value="">Todas</option>{(categories.data ?? []).map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
            <label>Vigencia<select value={params.is_active === undefined ? "" : String(params.is_active)} onChange={(event) => setParams({ ...params, is_active: event.target.value === "" ? undefined : event.target.value === "true" })}><option value="">Todas</option><option value="true">Activos</option><option value="false">Inactivos</option></select></label>
            <label>Estado<select value={params.state ?? ""} onChange={(event) => setParams({ ...params, state: event.target.value as ProjectReportParams["state"] || undefined })}><option value="">Todos</option><option value="NO_INICIADO">No iniciado</option><option value="EN_PROCESO">En proceso</option><option value="FINALIZADO">Finalizado</option></select></label>
          </div>
        )}
        {invalidPeriod ? <p role="alert">La fecha Desde debe ser anterior o igual a Hasta.</p> : null}
      </section>

      <section className="task-report-panel">
        <h2>Resumen</h2>
        {report.isPending && categories.isSuccess && !invalidPeriod ? (
          <p role="status">Cargando reporte…</p>
        ) : report.isError ? (
          <div role="alert"><p>No pudimos cargar el reporte.</p><button onClick={() => void report.refetch()}>Reintentar</button></div>
        ) : report.data ? (
          <>
            <dl className="pending-item-report-summary">
              <div><dt>Total</dt><dd>{report.data.summary.total_count}</dd></div>
              <div><dt>Activos</dt><dd>{report.data.summary.active_count}</dd></div>
              <div><dt>Inactivos</dt><dd>{report.data.summary.inactive_count}</dd></div>
              <div><dt>No iniciados</dt><dd>{report.data.summary.no_iniciado_count}</dd></div>
              <div><dt>En proceso</dt><dd>{report.data.summary.en_proceso_count}</dd></div>
              <div><dt>Finalizados</dt><dd>{report.data.summary.finalizado_count}</dd></div>
            </dl>

            <h3>Cumplimiento de Pasos</h3>
            <dl className="pending-item-report-summary compliance">
              <div><dt>En plazo</dt><dd>{report.data.step_compliance.en_plazo_count}</dd></div>
              <div><dt>Atrasados</dt><dd>{report.data.step_compliance.atrasado_count}</dd></div>
              <div><dt>Con adelanto</dt><dd>{report.data.step_compliance.con_adelanto_count}</dd></div>
              <div><dt>A tiempo</dt><dd>{report.data.step_compliance.a_tiempo_count}</dd></div>
              <div><dt>Con retraso</dt><dd>{report.data.step_compliance.con_retraso_count}</dd></div>
            </dl>

            <h3>Detalle de Pasos</h3>
            <dl className="pending-item-report-summary detail">
              <div><dt>Promedio de días de atraso</dt><dd>{metric(report.data.detail.average_atrasado_days)}</dd></div>
              <div><dt>Promedio de días de adelanto</dt><dd>{metric(report.data.detail.average_con_adelanto_days)}</dd></div>
              <div><dt>Promedio de días de retraso</dt><dd>{metric(report.data.detail.average_con_retraso_days)}</dd></div>
            </dl>

            {report.data.summary.total_count === 0 ? (
              <p className="review-empty">No hay Proyectos para los filtros seleccionados.</p>
            ) : (
              <div className="pending-item-report-table project-report-table">
                <table>
                  <caption className="sr-only">Resultados por proyecto</caption>
                  <thead><tr><th>Proyecto</th><th>Categoría</th><th>Vigencia</th><th>Fecha planificada</th><th>Avance</th><th>Estado</th><th>Cantidad de Pasos</th></tr></thead>
                  <tbody>{report.data.by_project.map((row) => <tr key={row.project_id}>
                    <th scope="row">{row.project_name}</th><td>{row.category_name}</td><td>{row.is_active ? "Activo" : "Inactivo"}</td><td>{row.planned_date ? formatShortCalendarDate(row.planned_date) : "—"}</td><td>{progress(row.progress)}</td><td>{row.state === null ? "—" : stateLabels[row.state]}</td><td>{row.step_count}</td>
                  </tr>)}</tbody>
                </table>
              </div>
            )}
          </>
        ) : null}
      </section>
    </section>
  );
}
