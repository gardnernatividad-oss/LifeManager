import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { queryKeys } from "../../api/queryKeys";
import { getCalendarComparison } from "../../api/v2CalendarComparisonApi";
import { getMyCalendar } from "../../api/v2CalendarApi";
import { listWorkspaceMembers } from "../../api/workspaceApi";
import { useAuth } from "../../hooks/useAuth";
import { useWorkspaces } from "../../hooks/useWorkspaces";
import { calendarRange, localCalendarDate } from "../../utils/calendarRange";

const time = (value: string, zone: string) => new Intl.DateTimeFormat("es-PE", { timeZone: zone, hour: "2-digit", minute: "2-digit" }).format(new Date(value));
const dayLabel = (value: string, zone: string) => new Intl.DateTimeFormat("es-PE", { timeZone: zone, weekday: "long", day: "2-digit", month: "long", year: "numeric" }).format(new Date(`${value}T12:00:00Z`));

export function CalendarComparisonPage() {
  const { user } = useAuth();
  const client = useQueryClient();
  const workspaces = useWorkspaces();
  const shared = useMemo(() => workspaces.data?.filter((item) => item.kind === "SHARED" && item.lifecycle === "ACTIVE") ?? [], [workspaces.data]);
  const [workspaceId, setWorkspaceId] = useState("");
  const [targetId, setTargetId] = useState("");
  const [day, setDay] = useState(() => user ? localCalendarDate(new Date(), user.timezone) : "");
  const range = useMemo(() => user && day ? calendarRange(day, "DAY", user.timezone) : null, [day, user]);
  const members = useQuery({ queryKey: queryKeys.workspaceMembers(workspaceId), queryFn: () => listWorkspaceMembers(workspaceId), enabled: Boolean(workspaceId) });
  const targets = members.data?.filter((item) => item.status === "ACTIVE" && item.user_id !== user?.id) ?? [];
  const own = useQuery({ queryKey: queryKeys.myCalendar(user?.id ?? "anonymous", range?.from ?? "", range?.to ?? ""), queryFn: () => getMyCalendar(range!.from, range!.to), enabled: Boolean(user && range) });
  const comparison = useQuery({
    queryKey: queryKeys.calendarComparison(user?.id ?? "anonymous", workspaceId, targetId, range?.from ?? "", range?.to ?? ""),
    queryFn: () => getCalendarComparison(workspaceId, targetId, range!.from, range!.to),
    enabled: Boolean(user && workspaceId && targetId && range),
  });
  if (!user || !range) return <section><h1>Comparar calendarios</h1><p>Cargando…</p></section>;
  return <section className="calendar-comparison-page">
    <Link className="back-link" to="/calendario">← Atrás</Link>
    <header><p className="eyebrow">Calendario compartido</p><h1>Comparar calendarios</h1></header>
    <div className="calendar-comparison-controls">
      <label>Workspace compartido<select aria-label="Workspace compartido" value={workspaceId} onChange={(event) => { setWorkspaceId(event.target.value); setTargetId(""); client.removeQueries({ queryKey: ["calendar-comparison"] }); }}><option value="">Selecciona</option>{shared.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label>Miembro<select aria-label="Miembro" value={targetId} disabled={!workspaceId || members.isPending} onChange={(event) => setTargetId(event.target.value)}><option value="">Selecciona</option>{targets.map((item) => <option key={item.user_id} value={item.user_id}>{item.display_name}</option>)}</select></label>
      <label>Día<input type="date" value={day} onChange={(event) => setDay(event.target.value)} /></label>
    </div>
    {workspaces.isError || members.isError ? <div role="alert"><p>No pudimos cargar las opciones de comparación.</p><button onClick={() => void (workspaces.isError ? workspaces.refetch() : members.refetch())}>Reintentar</button></div> : null}
    <h2>{dayLabel(day, user.timezone)}</h2>
    <div className="calendar-comparison-columns">
      <section><h3>Mi calendario</h3>{own.isPending ? <p>Cargando…</p> : own.data?.items.length ? own.data.items.map((item) => <article className="comparison-event comparison-event--own" key={item.activity_id}><strong>{item.activity_name}</strong><span>{time(item.starts_at, user.timezone)}–{time(item.ends_at, user.timezone)}</span></article>) : <p className="review-empty">Sin actividades.</p>}</section>
      <section><h3>Calendario comparado</h3>{!targetId ? <p className="review-empty">Selecciona un miembro.</p> : comparison.isPending ? <p role="status">Cargando comparación…</p> : comparison.isError ? <div role="alert"><p>No pudimos cargar la comparación.</p><button onClick={() => void comparison.refetch()}>Reintentar</button></div> : comparison.data.visibility === "HIDE" ? <p className="review-empty">Este usuario no comparte su calendario.</p> : comparison.data.visibility === "AVAILABILITY_ONLY" ? comparison.data.busy_blocks.length ? comparison.data.busy_blocks.map((block) => <article className="comparison-event comparison-event--busy" key={`${block.starts_at}-${block.ends_at}`}><strong>Ocupado</strong><span>{time(block.starts_at, user.timezone)}–{time(block.ends_at, user.timezone)}</span></article>) : <p className="review-empty">Sin bloques ocupados.</p> : comparison.data.detailed_events.length ? comparison.data.detailed_events.map((event) => <article className="comparison-event comparison-event--target" key={`${event.starts_at}-${event.ends_at}-${event.activity_name}`}><strong>{event.activity_name}</strong><span>{time(event.starts_at, user.timezone)}–{time(event.ends_at, user.timezone)}</span></article>) : <p className="review-empty">Sin actividades compartidas.</p>}</section>
    </div>
  </section>;
}
