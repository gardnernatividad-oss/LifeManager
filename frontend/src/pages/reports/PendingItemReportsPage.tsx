import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getPendingItemReport } from "../../api/pendingItemReportApi";
import { listAllCategoryOptions } from "../../api/planningPendingItemApi";
import { queryKeys } from "../../api/queryKeys";
import type { PendingItemReportParams } from "../../types/pendingItemReport";

const average = (value: string | number | null) =>
  value === null ? "—" : Number(value).toFixed(2);

export function PendingItemReportsPage() {
  const [params, setParams] = useState<PendingItemReportParams>({});
  const invalidPeriod = Boolean(
    params.planned_from && params.planned_to && params.planned_from > params.planned_to,
  );
  const categories = useQuery({
    queryKey: queryKeys.categoryOptions,
    queryFn: listAllCategoryOptions,
  });
  const report = useQuery({
    queryKey: queryKeys.pendingItemReports(params),
    queryFn: () => getPendingItemReport(params),
    enabled: !invalidPeriod && categories.isSuccess,
  });

  return (
    <section className="pending-item-report-page">
      <header>
        <p className="eyebrow">Reportes</p>
        <h1>Reportes · Pendientes</h1>
      </header>

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
          <div className="pending-item-report-filters">
            <label>
              Desde
              <input
                type="date"
                value={params.planned_from ?? ""}
                onChange={(event) =>
                  setParams({ ...params, planned_from: event.target.value || undefined })
                }
              />
            </label>
            <label>
              Hasta
              <input
                type="date"
                value={params.planned_to ?? ""}
                onChange={(event) =>
                  setParams({ ...params, planned_to: event.target.value || undefined })
                }
              />
            </label>
            <label>
              Categoría
              <select
                value={params.category_id ?? ""}
                onChange={(event) =>
                  setParams({ ...params, category_id: event.target.value || undefined })
                }
              >
                <option value="">Todas</option>
                {(categories.data ?? []).map((category) => (
                  <option key={category.id} value={category.id}>{category.name}</option>
                ))}
              </select>
            </label>
            <label>
              Vigencia
              <select
                value={params.is_active === undefined ? "" : String(params.is_active)}
                onChange={(event) =>
                  setParams({
                    ...params,
                    is_active: event.target.value === "" ? undefined : event.target.value === "true",
                  })
                }
              >
                <option value="">Todas</option>
                <option value="true">Activos</option>
                <option value="false">Inactivos</option>
              </select>
            </label>
            <label>
              Estado
              <select
                value={params.state ?? ""}
                onChange={(event) =>
                  setParams({ ...params, state: event.target.value as PendingItemReportParams["state"] || undefined })
                }
              >
                <option value="">Todos</option>
                <option value="NO_INICIADO">No iniciado</option>
                <option value="EN_PROCESO">En proceso</option>
                <option value="FINALIZADO">Finalizado</option>
              </select>
            </label>
            <label>
              Cumplimiento
              <select
                value={params.compliance ?? ""}
                onChange={(event) =>
                  setParams({ ...params, compliance: event.target.value as PendingItemReportParams["compliance"] || undefined })
                }
              >
                <option value="">Todos</option>
                <option value="EN_PLAZO">En plazo</option>
                <option value="ATRASADO">Atrasado</option>
                <option value="CON_ADELANTO">Con adelanto</option>
                <option value="A_TIEMPO">A tiempo</option>
                <option value="CON_RETRASO">Con retraso</option>
              </select>
            </label>
          </div>
        )}
        {invalidPeriod ? (
          <p role="alert">La fecha Desde debe ser anterior o igual a Hasta.</p>
        ) : null}
      </section>

      <section className="task-report-panel">
        <h2>Resumen</h2>
        {report.isPending && categories.isSuccess && !invalidPeriod ? (
          <p role="status">Cargando reporte…</p>
        ) : report.isError ? (
          <div role="alert">
            <p>No pudimos cargar el reporte.</p>
            <button onClick={() => void report.refetch()}>Reintentar</button>
          </div>
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

            <h3>Cumplimiento</h3>
            <dl className="pending-item-report-summary compliance">
              <div><dt>En plazo</dt><dd>{report.data.compliance.en_plazo_count}</dd></div>
              <div><dt>Atrasados</dt><dd>{report.data.compliance.atrasado_count}</dd></div>
              <div><dt>Con adelanto</dt><dd>{report.data.compliance.con_adelanto_count}</dd></div>
              <div><dt>A tiempo</dt><dd>{report.data.compliance.a_tiempo_count}</dd></div>
              <div><dt>Con retraso</dt><dd>{report.data.compliance.con_retraso_count}</dd></div>
            </dl>

            <h3>Detalle</h3>
            <dl className="pending-item-report-summary detail">
              <div><dt>Promedio de días de atraso</dt><dd>{average(report.data.detail.average_atrasado_days)}</dd></div>
              <div><dt>Promedio de días de adelanto</dt><dd>{average(report.data.detail.average_con_adelanto_days)}</dd></div>
              <div><dt>Promedio de días de retraso</dt><dd>{average(report.data.detail.average_con_retraso_days)}</dd></div>
            </dl>

            {report.data.summary.total_count === 0 ? (
              <p className="review-empty">No hay Pendientes para los filtros seleccionados.</p>
            ) : (
              <div className="pending-item-report-table">
                <table>
                  <caption className="sr-only">Resultados por categoría</caption>
                  <thead><tr><th>Categoría</th><th>Total</th><th>No iniciados</th><th>En proceso</th><th>Finalizados</th><th>En plazo</th><th>Atrasados</th><th>Con adelanto</th><th>A tiempo</th><th>Con retraso</th></tr></thead>
                  <tbody>{report.data.by_category.map((row) => (
                    <tr key={row.category_id}>
                      <th scope="row">{row.category_name}</th>
                      <td>{row.summary.total_count}</td>
                      <td>{row.summary.no_iniciado_count}</td>
                      <td>{row.summary.en_proceso_count}</td>
                      <td>{row.summary.finalizado_count}</td>
                      <td>{row.compliance.en_plazo_count}</td>
                      <td>{row.compliance.atrasado_count}</td>
                      <td>{row.compliance.con_adelanto_count}</td>
                      <td>{row.compliance.a_tiempo_count}</td>
                      <td>{row.compliance.con_retraso_count}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            )}
          </>
        ) : null}
      </section>
    </section>
  );
}
