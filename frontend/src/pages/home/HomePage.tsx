import { useQuery } from "@tanstack/react-query";

import { getHomeSummary } from "../../api/homeApi";
import { queryKeys } from "../../api/queryKeys";
import { useAuth } from "../../hooks/useAuth";

function formatLocalDate(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return value;
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]), 12));
  return `Hoy, ${new Intl.DateTimeFormat("es-PE", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC"
  }).format(date)}`;
}

function formatTimestamp(value: string | null, timeZone: string): string {
  if (!value) return "Sin registro";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Sin registro";
  return new Intl.DateTimeFormat("es-PE", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone
  }).format(parsed);
}

function HomeLoading() {
  return (
    <section className="home-page" aria-label="Inicio">
      <div className="home-skeleton" role="status" aria-label="Cargando Inicio">
        <span>Cargando Inicio…</span>
        <div className="home-skeleton__header" />
        <div className="home-summary-grid">
          {Array.from({ length: 4 }, (_, index) => <div className="home-skeleton__card" key={index} />)}
        </div>
      </div>
    </section>
  );
}

export function HomePage() {
  const { user } = useAuth();
  const homeQuery = useQuery({
    queryKey: queryKeys.home,
    queryFn: getHomeSummary
  });

  if (homeQuery.isPending) return <HomeLoading />;

  if (homeQuery.isError) {
    return (
      <section className="home-page">
        <h1>Inicio</h1>
        <div className="home-error" role="alert">
          <p>No pudimos cargar la información de Inicio.</p>
          <button className="secondary-button" type="button" onClick={() => void homeQuery.refetch()}>
            Reintentar
          </button>
        </div>
      </section>
    );
  }

  const data = homeQuery.data;
  const cards = [
    ["Tareas para hoy", data.tasks.due_today],
    ["Tareas vencidas", data.tasks.overdue],
    ["Pendientes vencidos", data.pending_items.overdue],
    ["Pasos vencidos", data.project_steps.overdue]
  ] as const;
  const noOverdue = data.tasks.overdue === 0
    && data.pending_items.overdue === 0
    && data.project_steps.overdue === 0;
  const timeZone = user?.timezone ?? "UTC";

  return (
    <section className="home-page">
      <header className="home-header">
        <div>
          <p className="eyebrow">{formatLocalDate(data.local_date)}</p>
          <h1>Bienvenido a LifeManager, {data.user_first_name}</h1>
        </div>
        <div className="home-refresh">
          <button
            className="secondary-button"
            type="button"
            aria-label="Actualizar Inicio"
            disabled={homeQuery.isFetching}
            onClick={() => void homeQuery.refetch()}
          >
            {homeQuery.isFetching ? "Actualizando…" : "Actualizar"}
          </button>
          {homeQuery.isFetching ? <span role="status">Actualizando información…</span> : null}
        </div>
      </header>

      <section aria-labelledby="home-attention-title">
        <h2 id="home-attention-title">Requiere atención</h2>
        <div className="home-summary-grid">
          {cards.map(([label, count]) => (
            <article className="home-summary-card" key={label}>
              <span>{label}</span>
              <strong>{count}</strong>
            </article>
          ))}
        </div>
        {noOverdue ? <p className="home-neutral-state">No hay elementos vencidos.</p> : null}
      </section>

      <dl className="home-timestamps" aria-label="Últimas actualizaciones">
        <div>
          <dt>Última revisión</dt>
          <dd>{formatTimestamp(data.last_review_saved_at, timeZone)}</dd>
        </div>
        <div>
          <dt>Última actualización de pendientes</dt>
          <dd>{formatTimestamp(data.pending_items_last_tracking_saved_at, timeZone)}</dd>
        </div>
      </dl>
    </section>
  );
}
