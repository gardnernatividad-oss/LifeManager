import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getV2HomeSummary } from "../../api/homeApi";
import { queryKeys } from "../../api/queryKeys";
import { useAuth } from "../../hooks/useAuth";
import type { HomeAttentionItem, HomeWorkspace } from "../../types/v2Home";
import { activityLocalDate } from "../../utils/calendarRange";
import { formatCalendarDate, formatLocalTimestamp, formatShortCalendarDate } from "../../utils/localizedDate";

function WorkspaceMark({ workspace }: { workspace: HomeWorkspace }) { return <span className={`home-workspace home-workspace--${workspace.color.toLowerCase()}`}><span aria-hidden="true">{workspace.icon}</span>{workspace.name}</span>; }
function attentionPath(item: HomeAttentionItem) { if (item.type === "PENDING_ITEM") return `/planificacion/pendientes/${item.id}`; if (item.type === "PROJECT_STAGE" && item.project_id) return `/seguimiento/proyectos/${item.project_id}/etapas/${item.id}`; return "/seguimiento/tareas"; }

export function HomePage() {
  const { user } = useAuth();
  const query = useQuery({ queryKey: queryKeys.v2Home, queryFn: getV2HomeSummary });
  if (query.isPending) return <section className="home-page" aria-label="Inicio"><p role="status">Cargando Inicio…</p></section>;
  if (query.isError) return <section className="home-page"><h1>Inicio</h1><div className="home-error" role="alert"><p>No pudimos cargar Inicio.</p><button type="button" onClick={() => void query.refetch()}>Reintentar</button></div></section>;
  const { data } = query;
  const cards = [["Tareas", data.today.tasks, "/seguimiento/tareas"], ["Pendientes", data.today.pending_items, "/seguimiento/pendientes"], ["Etapas", data.today.project_stages, "/seguimiento/proyectos"], ["Actividades", data.today.activities, `/calendario?date=${data.local_date}`]] as const;
  const timeZone = user?.timezone ?? "UTC";
  return <section className="home-page">
    <header className="home-header"><div><p className="eyebrow">Resumen global</p><h1>Inicio</h1><p>{formatCalendarDate(data.local_date, "Hoy")}</p></div></header>
    <section aria-labelledby="home-today"><h2 id="home-today">Hoy</h2><div className="home-today-grid">{cards.map(([label, count, path]) => <Link className="home-today-card" to={path} key={label}><span>{label}</span><strong>{count}</strong></Link>)}</div></section>
    <section aria-labelledby="home-activities"><h2 id="home-activities">Próximas Actividades</h2>{data.upcoming_activities.length ? <ul className="home-action-list">{data.upcoming_activities.map((item) => <li key={item.id}><Link to={`/calendario?date=${activityLocalDate(item.starts_at, timeZone)}&activity=${item.id}`}><strong>{item.name}</strong><span>{formatLocalTimestamp(item.starts_at, timeZone)} – {formatLocalTimestamp(item.ends_at, timeZone)}</span><WorkspaceMark workspace={item.workspace} /></Link></li>)}</ul> : <p className="review-empty">No hay Actividades próximas.</p>}</section>
    <section aria-labelledby="home-attention"><h2 id="home-attention">Requieren atención</h2>{data.attention.length ? <ul className="home-action-list">{data.attention.map((item) => <li key={`${item.type}-${item.id}`}><Link to={attentionPath(item)}><span className="status-badge">{item.type === "TASK" ? "Tarea" : item.type === "PENDING_ITEM" ? "Pendiente" : "Etapa"}</span><strong>{item.name}</strong><span>{formatShortCalendarDate(item.planned_date)}</span><WorkspaceMark workspace={item.workspace} /></Link></li>)}</ul> : <p className="review-empty">Nada requiere atención.</p>}</section>
    <section aria-labelledby="home-days"><h2 id="home-days">Próximos días</h2><div className="home-days">{data.upcoming_days.map((day) => <article key={day.date}><h3>{formatCalendarDate(day.date)}</h3><dl><div><dt>Tareas</dt><dd>{day.tasks}</dd></div><div><dt>Pendientes</dt><dd>{day.pending_items}</dd></div><div><dt>Etapas</dt><dd>{day.project_stages}</dd></div><div><dt>Actividades</dt><dd>{day.activities}</dd></div></dl></article>)}</div></section>
  </section>;
}
