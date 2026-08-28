import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { queryKeys } from "../../api/queryKeys";
import { deleteV2Activity, leaveV2Activity } from "../../api/v2ActivityApi";
import { getMyCalendar } from "../../api/v2CalendarApi";
import { useAuth } from "../../hooks/useAuth";
import type { CalendarActivity } from "../../types/v2Calendar";
import { activityLocalDate, addCalendarDays, calendarRange, localCalendarDate, type CalendarView } from "../../utils/calendarRange";

const dateLabel = (value: string, timeZone: string, weekday = false) => new Intl.DateTimeFormat("es-PE", {
  timeZone, day: "2-digit", month: "short", year: "numeric", ...(weekday ? { weekday: "short" as const } : {}),
}).format(new Date(`${value}T12:00:00Z`));
const timeLabel = (value: string, timeZone: string) => new Intl.DateTimeFormat("es-PE", { timeZone, hour: "2-digit", minute: "2-digit" }).format(new Date(value));
const workspaceTone = (id: string) => [...id].reduce((value, char) => (value * 31 + char.charCodeAt(0)) >>> 0, 0) % 6;

export function MyCalendarPage() {
  const { user } = useAuth();
  const client = useQueryClient();
  const [view, setView] = useState<CalendarView>(() => window.matchMedia("(max-width: 48rem)").matches ? "DAY" : "WEEK");
  const [anchor, setAnchor] = useState(() => user ? localCalendarDate(new Date(), user.timezone) : "");
  const [selected, setSelected] = useState<CalendarActivity | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const range = useMemo(() => user && anchor ? calendarRange(anchor, view, user.timezone) : null, [anchor, user, view]);
  const calendar = useQuery({ queryKey: queryKeys.myCalendar(user?.id ?? "anonymous", range?.from ?? "", range?.to ?? ""), queryFn: () => getMyCalendar(range!.from, range!.to), enabled: Boolean(user && range) });
  const refresh = async (item: CalendarActivity) => {
    await Promise.all([client.invalidateQueries({ queryKey: queryKeys.myCalendarRoot(user!.id) }), client.invalidateQueries({ queryKey: queryKeys.v2ActivitiesRoot(item.workspace.id) })]);
  };
  const mutation = useMutation({ mutationFn: (operation: () => Promise<unknown>) => operation(), onSuccess: async (_, operation) => { void operation; const item = selected!; setSelected(null); setFeedback("Calendario actualizado."); await refresh(item); }, onError: async () => { const item = selected; setFeedback("No pudimos actualizar la Actividad."); if (item) await refresh(item); } });
  if (!user || !range) return <section><h1>Mi calendario</h1><p>Cargando calendario…</p></section>;
  const days = Array.from({ length: view === "WEEK" ? 7 : 1 }, (_, index) => addCalendarDays(range.first, index));
  const move = (direction: number) => setAnchor(addCalendarDays(anchor, direction * (view === "WEEK" ? 7 : 1)));
  return <section className="my-calendar-page"><header><p className="eyebrow">Calendario personal</p><h1>Mi calendario</h1><Link className="primary-button" to="/calendario/comparar">Comparar</Link></header>
    <div className="calendar-toolbar" aria-label="Navegación del calendario"><div><button type="button" aria-label="Periodo anterior" onClick={() => move(-1)}>‹</button><button type="button" onClick={() => setAnchor(localCalendarDate(new Date(), user.timezone))}>Hoy</button><button type="button" aria-label="Periodo siguiente" onClick={() => move(1)}>›</button></div><strong>{view === "WEEK" ? `${dateLabel(range.first, user.timezone)} – ${dateLabel(addCalendarDays(range.after, -1), user.timezone)}` : dateLabel(range.first, user.timezone, true)}</strong><div role="group" aria-label="Vista del calendario"><button type="button" aria-pressed={view === "DAY"} onClick={() => setView("DAY")}>Día</button><button type="button" aria-pressed={view === "WEEK"} onClick={() => setView("WEEK")}>Semana</button></div></div>
    {feedback ? <p role="status">{feedback}</p> : null}
    {calendar.isPending ? <p role="status">Cargando calendario…</p> : calendar.isError ? <div role="alert"><p>No pudimos cargar Mi calendario.</p><button type="button" onClick={() => void calendar.refetch()}>Reintentar</button></div> : calendar.data.items.length === 0 ? <p className="review-empty">No hay Actividades en este periodo.</p> : <div className={view === "WEEK" ? "calendar-grid calendar-grid--week" : "calendar-grid calendar-grid--day"}>{days.map((day) => <section className="calendar-day" key={day} aria-label={dateLabel(day, user.timezone, true)}><h2>{dateLabel(day, user.timezone, true)}</h2><div className="calendar-day__activities">{calendar.data.items.filter((item) => activityLocalDate(item.starts_at, user.timezone) === day).map((item) => <button type="button" className={`calendar-activity calendar-activity--tone-${workspaceTone(item.workspace.id)}`} key={item.activity_id} onClick={() => setSelected(item)}><strong>{item.activity_name}</strong><span>{timeLabel(item.starts_at, user.timezone)}–{timeLabel(item.ends_at, user.timezone)}</span><small>{item.workspace.name}</small></button>)}</div></section>)}</div>}
    {selected ? <dialog open className="calendar-detail"><h2>{selected.activity_name}</h2><p>{dateLabel(activityLocalDate(selected.starts_at, user.timezone), user.timezone, true)}</p><p>{timeLabel(selected.starts_at, user.timezone)}–{timeLabel(selected.ends_at, user.timezone)}</p><p><strong>Workspace:</strong> {selected.workspace.name}</p><p><strong>Categoría:</strong> {selected.category_name}</p><p><strong>Organizador:</strong> {selected.organizer.display_name}</p><p><strong>Participantes:</strong> {selected.participants.map((item) => item.display_name).join(", ") || "Sin participantes"}</p><p>{selected.temporal_state === "FUTURE" ? "Próxima" : selected.temporal_state === "IN_PROGRESS" ? "En curso" : "Finalizada"}</p><div>{selected.can_delete ? <button type="button" disabled={mutation.isPending} onClick={() => mutation.mutate(() => deleteV2Activity(selected.workspace.id, selected.activity_id, selected.lock_version))}>Eliminar</button> : null}{selected.can_leave_participation ? <button type="button" disabled={mutation.isPending} onClick={() => mutation.mutate(() => leaveV2Activity(selected.workspace.id, selected.activity_id, selected.lock_version))}>Retirarme</button> : null}<button type="button" onClick={() => setSelected(null)}>Cerrar</button></div></dialog> : null}
  </section>;
}
