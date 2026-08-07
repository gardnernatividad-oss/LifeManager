import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { getDashboardStatistics, getDashboardSummary } from "../../api/dashboardApi";
import { queryKeys } from "../../api/queryKeys";
import { useAuth } from "../../hooks/useAuth";
import { useWorkspaces } from "../../hooks/useWorkspaces";
import type { DashboardStatistics, DashboardSummary } from "../../types/dashboard";

const summaryMetrics: Array<[keyof DashboardSummary, string]> = [
  ["pending_tasks", "Pendientes"],
  ["scheduled_tasks", "Programadas"],
  ["completed_tasks", "Completadas"],
  ["not_completed_tasks", "No realizadas"],
  ["cancelled_tasks", "Canceladas"],
  ["total_tasks", "Total"],
  ["tasks_due_today", "Para hoy"],
  ["tasks_due_next_7_days", "Próximos 7 días"],
  ["overdue_tasks", "Vencidas"]
];

const statisticsMetrics: Array<[keyof DashboardStatistics, string]> = [
  ["completed_tasks", "Completadas"],
  ["not_completed_tasks", "No realizadas"],
  ["cancelled_tasks", "Canceladas"],
  ["resolved_tasks", "Resueltas"],
  ["pending_tasks", "Pendientes"],
  ["scheduled_tasks", "Programadas"]
];

function DashboardLoading() {
  return (
    <div className="dashboard-skeleton" role="status" aria-label="Cargando Dashboard">
      <div className="skeleton-block skeleton-block--wide" />
      <div className="dashboard-metrics">
        {Array.from({ length: 6 }, (_, index) => (
          <div className="skeleton-block skeleton-block--card" key={index} />
        ))}
      </div>
    </div>
  );
}

function ErrorPanel({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="dashboard-error" role="alert">
      <p>{message}</p>
      <button className="secondary-button" type="button" onClick={onRetry}>
        Reintentar
      </button>
    </div>
  );
}

function QuickNavigation() {
  return (
    <section className="dashboard-section" aria-labelledby="quick-navigation-title">
      <h2 id="quick-navigation-title">Accesos rápidos</h2>
      <div className="quick-links">
        <Link to="/tasks">Tareas</Link>
        <Link to="/tasks/recurring">Tareas recurrentes</Link>
        <Link to="/daily-workflow">Seguimiento diario</Link>
        <Link to="/projects">Proyectos</Link>
      </div>
    </section>
  );
}

export function DashboardPage() {
  const { user, workspace } = useAuth();
  const workspacesQuery = useWorkspaces();
  const workspaceId = workspace?.id ?? "";
  const summaryQuery = useQuery({
    queryKey: queryKeys.dashboardSummary(workspaceId),
    queryFn: () => getDashboardSummary(workspaceId),
    enabled: Boolean(workspaceId),
    staleTime: 30_000
  });
  const statisticsQuery = useQuery({
    queryKey: queryKeys.dashboardStatistics(workspaceId),
    queryFn: () => getDashboardStatistics(workspaceId),
    enabled: Boolean(workspaceId),
    staleTime: 30_000
  });

  if (workspacesQuery.isPending) {
    return <DashboardLoading />;
  }

  if (workspacesQuery.isError) {
    return (
      <ErrorPanel
        message="No pudimos cargar tus espacios de trabajo. Verifica la conexión e intenta nuevamente."
        onRetry={() => void workspacesQuery.refetch()}
      />
    );
  }

  if (workspacesQuery.data.length === 0) {
    return (
      <div className="dashboard-page">
        <header className="dashboard-header">
          <div><p className="eyebrow">LifeManager</p><h1>Dashboard</h1></div>
        </header>
        <section className="dashboard-empty" aria-labelledby="no-workspaces-title">
          <h2 id="no-workspaces-title">No tienes un espacio de trabajo disponible</h2>
          <p>Cuando tengas acceso a uno, aquí verás tus tareas y resultados.</p>
        </section>
      </div>
    );
  }

  if (!workspace) {
    return <DashboardLoading />;
  }

  const isRefreshing = summaryQuery.isFetching || statisticsQuery.isFetching;
  const updatedAt = Math.max(summaryQuery.dataUpdatedAt, statisticsQuery.dataUpdatedAt);

  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">{workspace.name}</p>
          <h1>Hola, {user?.first_name}. Este es tu Dashboard</h1>
          <p>Revisa lo que necesita atención y el avance de tus tareas.</p>
        </div>
        <div className="dashboard-refresh">
          <button
            className="secondary-button"
            type="button"
            disabled={isRefreshing}
            onClick={() => void Promise.all([summaryQuery.refetch(), statisticsQuery.refetch()])}
          >
            {isRefreshing ? "Actualizando…" : "Actualizar Dashboard"}
          </button>
          {updatedAt > 0 ? (
            <span>Actualizado {new Intl.DateTimeFormat("es-PE", { hour: "2-digit", minute: "2-digit" }).format(updatedAt)}</span>
          ) : null}
        </div>
      </header>

      {summaryQuery.isPending ? <DashboardLoading /> : null}
      {summaryQuery.isError ? (
        <ErrorPanel
          message="No pudimos cargar el resumen de tareas."
          onRetry={() => void summaryQuery.refetch()}
        />
      ) : null}
      {summaryQuery.data ? (
        <>
          {summaryQuery.data.total_tasks === 0 ? (
            <section className="dashboard-empty" aria-label="Espacio sin tareas">
              <h2>Tu espacio todavía no tiene tareas</h2>
              <p>Usa los accesos rápidos para comenzar a organizar tu planificación.</p>
            </section>
          ) : null}
          <section className="dashboard-section" aria-labelledby="attention-title">
            <h2 id="attention-title">Requiere atención</h2>
            <div className="attention-grid">
              <article className="attention-card attention-card--overdue">
                <span>Vencidas</span><strong>{summaryQuery.data.overdue_tasks}</strong>
                <small>Tareas sin resolver de fechas anteriores</small>
              </article>
              <article className="attention-card">
                <span>Para hoy</span><strong>{summaryQuery.data.tasks_due_today}</strong>
                <small>Tareas previstas para el día de hoy</small>
              </article>
              <article className="attention-card">
                <span>Pendientes</span><strong>{summaryQuery.data.pending_tasks}</strong>
                <small>Tareas que aún necesitan resolución</small>
              </article>
            </div>
          </section>
          <section className="dashboard-section" aria-labelledby="metrics-title">
            <h2 id="metrics-title">Resumen de tareas</h2>
            <div className="dashboard-metrics">
              {summaryMetrics.map(([field, label]) => (
                <article className="metric-card" key={field}>
                  <span>{label}</span><strong>{summaryQuery.data[field]}</strong>
                </article>
              ))}
            </div>
          </section>
        </>
      ) : null}

      <section className="dashboard-section" aria-labelledby="completion-title">
        <h2 id="completion-title">Resultados de finalización</h2>
        {statisticsQuery.isPending ? <div className="skeleton-block skeleton-block--wide" role="status" aria-label="Cargando estadísticas" /> : null}
        {statisticsQuery.isError ? (
          <ErrorPanel
            message="El resumen está disponible, pero no pudimos cargar las estadísticas."
            onRetry={() => void statisticsQuery.refetch()}
          />
        ) : null}
        {statisticsQuery.data ? (
          <div className="completion-panel">
            <div className="completion-rate">
              <span>Tasa de finalización</span>
              <strong>{statisticsQuery.data.completion_rate.toFixed(2)}%</strong>
              <div
                className="progress-track"
                role="progressbar"
                aria-label="Tasa de finalización"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={statisticsQuery.data.completion_rate}
              >
                <span style={{ width: `${statisticsQuery.data.completion_rate}%` }} />
              </div>
            </div>
            <dl className="statistics-grid">
              {statisticsMetrics.map(([field, label]) => (
                <div key={field}><dt>{label}</dt><dd>{statisticsQuery.data[field]}</dd></div>
              ))}
            </dl>
          </div>
        ) : null}
      </section>

      <QuickNavigation />
    </div>
  );
}
