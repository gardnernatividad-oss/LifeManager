import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { queryKeys } from "../../api/queryKeys";
import { createRecurringV2Activities, createV2Activity, deleteV2Activity, leaveV2Activity, listV2Activities, updateV2Activity } from "../../api/v2ActivityApi";
import { listWorkspaceMembers, type WorkspaceMemberSummary } from "../../api/workspaceApi";
import { ActivityCatalogSelector, CategorySelector } from "../../components/common/V2CatalogSelector";
import { useAuth } from "../../hooks/useAuth";
import type { WorkspaceSummary } from "../../types/auth";
import type { ActivityMutationScope, ActivityRecurrencePattern, V2Activity, V2ActivityFilters, V2ActivityUpdate } from "../../types/v2Activity";
import { activityRecurrenceDates } from "../../utils/activityRecurrence";
import { formatTaskDate, isoToLocalInput, localDateTimeToIso } from "../../utils/taskDateTime";

const safeError = (error: unknown) => axios.isAxiosError(error) && error.response?.status === 409
  ? "La Actividad cambió o ya comenzó. Actualizamos los datos; vuelve a intentarlo."
  : "No pudimos guardar la Actividad.";

export function PlanningActivitiesPage() {
  const { workspace, user } = useAuth();
  if (!workspace || !user) return <section><h1>Planificación · Actividades</h1><p>Selecciona un espacio.</p></section>;
  return <WorkspaceActivities key={workspace.id} workspace={workspace} userId={user.id} timeZone={user.timezone} />;
}

function WorkspaceActivities({ workspace, userId, timeZone }: { workspace: WorkspaceSummary; userId: string; timeZone: string }) {
  const client = useQueryClient();
  const shared = workspace.kind === "SHARED";
  const [filters, setFilters] = useState<V2ActivityFilters>({ page: 1, page_size: 25 });
  const [masterId, setMasterId] = useState("");
  const [customName, setCustomName] = useState("");
  const [customCategoryId, setCustomCategoryId] = useState("");
  const [organizerId, setOrganizerId] = useState("");
  const [participants, setParticipants] = useState<string[]>([]);
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [mode, setMode] = useState<"ONCE" | "REPEAT">("ONCE");
  const [pattern, setPattern] = useState<ActivityRecurrencePattern>("DAILY");
  const [dateFrom, setDateFrom] = useState("");
  const [dateUntil, setDateUntil] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [weekdays, setWeekdays] = useState<number[]>([]);
  const [monthDays, setMonthDays] = useState("");
  const [editing, setEditing] = useState<V2Activity | null>(null);
  const [scopeAction, setScopeAction] = useState<{ activity: V2Activity; kind: "DELETE" | "LEAVE" } | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const activities = useQuery({ queryKey: queryKeys.v2Activities(workspace.id, filters), queryFn: () => listV2Activities(workspace.id, filters) });
  const members = useQuery({ queryKey: queryKeys.workspaceMembers(workspace.id), queryFn: () => listWorkspaceMembers(workspace.id), enabled: shared });
  const activeMembers = (members.data ?? []).filter((member) => member.status === "ACTIVE");
  const refresh = () => Promise.all([
    client.invalidateQueries({ queryKey: queryKeys.v2ActivitiesRoot(workspace.id) }),
    client.invalidateQueries({ queryKey: queryKeys.myCalendarRoot(userId) }),
    client.invalidateQueries({ queryKey: ["calendar-comparison"] }),
  ]);
  const mutation = useMutation({
    mutationFn: (operation: () => Promise<unknown>) => operation(),
    onSuccess: async () => { setEditing(null); setFeedback("Cambios guardados."); await refresh(); },
    onError: async (error) => { setEditing(null); setFeedback(safeError(error)); await refresh(); },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    try {
      if (!masterId || (masterId === "__custom__" && (!customName.trim() || !customCategoryId)) || (shared && !organizerId)) throw new Error("Completa los campos requeridos.");
      const source = masterId === "__custom__" ? { custom_name: customName, custom_category_id: customCategoryId } : { activity_master_id: masterId };
      if (mode === "REPEAT") {
        const days = monthDays.split(",").map((value) => Number(value.trim())).filter((value) => Number.isInteger(value));
        const dates = activityRecurrenceDates({ pattern, dateFrom, dateUntil, weekdays, monthDays: days });
        const invalidMonthlyDays = pattern === "MONTHLY" && (days.length === 0 || new Set(days).size !== days.length || days.some((day) => day < 1 || day > 31));
        if (!dateFrom || !dateUntil || dateUntil < dateFrom || !startTime || !endTime || endTime <= startTime ||
            (pattern === "WEEKLY" && weekdays.length === 0) || invalidMonthlyDays || dates.length === 0 || dates.length > 1000) {
          throw new Error("Completa una recurrencia válida de hasta 1000 ocurrencias.");
        }
        mutation.mutate(() => createRecurringV2Activities(workspace.id, {
          ...source, ...(shared ? { organizer_user_id: organizerId } : {}),
          participant_user_ids: shared ? participants : [], start_time: startTime, end_time: endTime,
          timezone: timeZone, recurrence: { pattern, date_from: dateFrom, date_until: dateUntil,
            ...(pattern === "WEEKLY" ? { weekdays } : {}), ...(pattern === "MONTHLY" ? { month_days: days } : {}) },
        }).then((value) => { setDateFrom(""); setDateUntil(""); setParticipants([]); return value; }));
        return;
      }
      if (!startsAt || !endsAt) throw new Error("Completa los campos requeridos.");
      mutation.mutate(() => createV2Activity(workspace.id, {
        ...source,
        ...(shared ? { organizer_user_id: organizerId } : {}),
        participant_user_ids: shared ? participants : [],
        starts_at: localDateTimeToIso(startsAt, timeZone), ends_at: localDateTimeToIso(endsAt, timeZone),
      }).then((value) => { setStartsAt(""); setEndsAt(""); setParticipants([]); return value; }));
    } catch (error) { setFeedback(error instanceof Error ? error.message : "Fecha u hora inválida."); }
  }

  return <section className="v2-activity-page"><header><p className="eyebrow">Planificación</p><h1>Planificación · Actividades</h1></header>
    <section className="project-planning-panel"><h2>Crear Actividad</h2><form className="v2-activity-form" onSubmit={submit}>
      <fieldset><legend>Modalidad</legend><label><input type="radio" checked={mode === "ONCE"} onChange={() => setMode("ONCE")} />Una vez</label><label><input type="radio" checked={mode === "REPEAT"} onChange={() => setMode("REPEAT")} />Repetir</label></fieldset>
      <ActivityCatalogSelector workspaceId={workspace.id} value={masterId} onChange={(value) => { setMasterId(value); setCustomName(""); setCustomCategoryId(""); }} includeCustomOption required />
      {masterId === "__custom__" ? <><label>Nombre<input value={customName} maxLength={255} onChange={(event) => setCustomName(event.target.value)} required /></label><CategorySelector workspaceId={workspace.id} value={customCategoryId} onChange={setCustomCategoryId} required /></> : null}
      {shared ? <MemberSelect label="Organizador" value={organizerId} members={activeMembers} onChange={setOrganizerId} required /> : <p>Organizador: tú</p>}
      {mode === "ONCE" ? <><label>Inicio<input type="datetime-local" required value={startsAt} onChange={(event) => setStartsAt(event.target.value)} /></label><label>Fin<input type="datetime-local" required value={endsAt} onChange={(event) => setEndsAt(event.target.value)} /></label></> : <>
        <label>Frecuencia<select value={pattern} onChange={(event) => setPattern(event.target.value as ActivityRecurrencePattern)}><option value="DAILY">Diaria</option><option value="WEEKLY">Semanal</option><option value="MONTHLY">Mensual</option></select></label>
        <label>Desde<input type="date" required value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} /></label><label>Hasta<input type="date" required value={dateUntil} onChange={(event) => setDateUntil(event.target.value)} /></label>
        <label>Hora de inicio<input type="time" required value={startTime} onChange={(event) => setStartTime(event.target.value)} /></label><label>Hora de fin<input type="time" required value={endTime} onChange={(event) => setEndTime(event.target.value)} /></label>
        {pattern === "WEEKLY" ? <fieldset><legend>Días</legend>{["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"].map((label, day) => <label key={label}><input type="checkbox" checked={weekdays.includes(day)} onChange={(event) => setWeekdays(event.target.checked ? [...weekdays, day] : weekdays.filter((value) => value !== day))} />{label}</label>)}</fieldset> : null}
        {pattern === "MONTHLY" ? <label>Días del mes<input value={monthDays} placeholder="1, 15, 31" onChange={(event) => setMonthDays(event.target.value)} /><small>Si un día no existe, se usa el último día del mes.</small></label> : null}
        <p>{activityRecurrenceDates({ pattern, dateFrom, dateUntil, weekdays, monthDays: monthDays.split(",").map(Number).filter(Number.isInteger) }).length} ocurrencias</p>
      </>}
      {shared ? <ParticipantChecks members={activeMembers} selected={participants} onChange={setParticipants} /> : null}
      <button className="primary-button" disabled={mutation.isPending}>Crear</button>
    </form></section>
    <section className="project-planning-panel"><h2>Registro de Actividades</h2>
      <div className="v2-activity-filters"><ActivityCatalogSelector workspaceId={workspace.id} value={filters.custom ? "__custom__" : filters.activity_master_id ?? ""} onChange={(value) => setFilters({ ...filters, page: 1, activity_master_id: value && value !== "__custom__" ? value : undefined, custom: value === "__custom__" ? true : undefined })} includeCustomOption />{shared ? <MemberSelect label="Organizador" value={filters.organizer_user_id ?? ""} members={activeMembers} onChange={(value) => setFilters({ ...filters, page: 1, organizer_user_id: value || undefined })} /> : null}</div>
      {feedback ? <p role="status">{feedback}</p> : null}
      {activities.isPending ? <p role="status">Cargando Actividades…</p> : activities.isError ? <div role="alert"><p>No pudimos cargar las Actividades.</p><button type="button" onClick={() => void activities.refetch()}>Reintentar</button></div> : activities.data.items.length === 0 ? <p className="review-empty">No existen Actividades.</p> : <div className="v2-activity-list">{activities.data.items.map((activity) => <ActivityRow key={activity.id} activity={activity} shared={shared} timeZone={timeZone} pending={mutation.isPending} onEdit={() => setEditing(activity)} onDelete={() => activity.is_generated ? setScopeAction({ activity, kind: "DELETE" }) : mutation.mutate(() => deleteV2Activity(workspace.id, activity.id, activity.lock_version))} onLeave={() => activity.is_generated ? setScopeAction({ activity, kind: "LEAVE" }) : mutation.mutate(() => leaveV2Activity(workspace.id, activity.id, activity.lock_version))} />)}</div>}
      {activities.data ? <div className="planning-pagination"><span>Página {activities.data.page} de {Math.max(1, activities.data.total_pages)}</span><label>Por página<select value={filters.page_size} onChange={(event) => setFilters({ ...filters, page: 1, page_size: Number(event.target.value) })}><option>25</option><option>50</option><option>100</option></select></label><button type="button" disabled={filters.page <= 1} onClick={() => setFilters({ ...filters, page: filters.page - 1 })}>Anterior</button><button type="button" disabled={filters.page >= activities.data.total_pages} onClick={() => setFilters({ ...filters, page: filters.page + 1 })}>Siguiente</button></div> : null}
    </section>
    {editing ? <EditDialog activity={editing} workspace={workspace} timeZone={timeZone} members={activeMembers} pending={mutation.isPending} onClose={() => setEditing(null)} onSave={(payload) => mutation.mutate(() => updateV2Activity(workspace.id, editing.id, payload))} /> : null}
    {scopeAction ? <ScopeDialog action={scopeAction.kind} shared={shared} onClose={() => setScopeAction(null)} onConfirm={(scope) => { const { activity, kind } = scopeAction; setScopeAction(null); mutation.mutate(() => kind === "DELETE" ? deleteV2Activity(workspace.id, activity.id, activity.lock_version, scope) : leaveV2Activity(workspace.id, activity.id, activity.lock_version, scope)); }} /> : null}
  </section>;
}

function MemberSelect({ label, value, members, onChange, required }: { label: string; value: string; members: WorkspaceMemberSummary[]; onChange: (value: string) => void; required?: boolean }) { return <label>{label}<select value={value} required={required} onChange={(event) => onChange(event.target.value)}><option value="">{required ? "Selecciona una persona" : "Todas"}</option>{members.map((member) => <option key={member.user_id} value={member.user_id}>{member.display_name}</option>)}</select></label>; }
function ParticipantChecks({ members, selected, onChange }: { members: WorkspaceMemberSummary[]; selected: string[]; onChange: (value: string[]) => void }) { return <fieldset><legend>Participantes</legend>{members.map((member) => <label key={member.user_id}><input type="checkbox" checked={selected.includes(member.user_id)} onChange={(event) => onChange(event.target.checked ? [...selected, member.user_id] : selected.filter((id) => id !== member.user_id))} />{member.display_name}</label>)}</fieldset>; }
function ActivityRow({ activity, shared, timeZone, pending, onEdit, onDelete, onLeave }: { activity: V2Activity; shared: boolean; timeZone: string; pending: boolean; onEdit: () => void; onDelete: () => void; onLeave: () => void }) { const label = activity.status === "CANCELLED" ? "Cancelada" : activity.temporal_state === "FUTURE" ? "Próxima" : activity.temporal_state === "IN_PROGRESS" ? "En curso" : "Finalizada"; return <article className="v2-activity-row"><div><strong>{activity.title}</strong><small>{activity.category_name} · {activity.organizer_display_name}</small></div><span>{formatTaskDate(activity.starts_at, timeZone)} – {formatTaskDate(activity.ends_at, timeZone)}</span><span>{label}</span><div>{activity.can_edit ? <button type="button" onClick={onEdit}>Editar</button> : null}{activity.can_delete ? <button type="button" disabled={pending} onClick={onDelete}>{shared ? "Cancelar" : "Eliminar"}</button> : null}{activity.can_leave_participation ? <button type="button" disabled={pending} onClick={onLeave}>Retirarme</button> : null}</div></article>; }
function EditDialog({ activity, workspace, timeZone, members, pending, onClose, onSave }: { activity: V2Activity; workspace: WorkspaceSummary; timeZone: string; members: WorkspaceMemberSummary[]; pending: boolean; onClose: () => void; onSave: (payload: V2ActivityUpdate) => void }) { const shared = workspace.kind === "SHARED"; const [scope, setScope] = useState<ActivityMutationScope>("THIS"); const [masterId, setMasterId] = useState(activity.activity_master_id ?? ""); const [customName, setCustomName] = useState(activity.title); const [customCategoryId, setCustomCategoryId] = useState(activity.custom_category_id ?? ""); const [organizerId, setOrganizerId] = useState(activity.organizer_user_id); const [selected, setSelected] = useState(activity.participants.map((item) => item.user_id)); const [error, setError] = useState<string | null>(null); return <dialog open><form onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); try { const source = activity.is_custom ? { custom_name: customName, custom_category_id: customCategoryId } : { activity_master_id: masterId }; onSave({ ...source, ...(shared ? { organizer_user_id: organizerId, participant_user_ids: selected } : {}), starts_at: localDateTimeToIso(String(data.get("starts_at")), timeZone), ends_at: localDateTimeToIso(String(data.get("ends_at")), timeZone), lock_version: activity.lock_version, scope }); } catch (caught) { setError(caught instanceof Error ? caught.message : "Fecha u hora inválida."); } }}><h2>Editar {activity.title}</h2>{activity.is_generated ? <fieldset><legend>Aplicar a</legend><label><input type="radio" checked={scope === "THIS"} onChange={() => setScope("THIS")} />Solo esta</label><label><input type="radio" checked={scope === "THIS_AND_FUTURE"} onChange={() => setScope("THIS_AND_FUTURE")} />Esta y todas las futuras</label></fieldset> : null}{activity.is_custom ? <><label>Nombre<input value={customName} maxLength={255} onChange={(event) => setCustomName(event.target.value)} required /></label><CategorySelector workspaceId={workspace.id} currentId={activity.custom_category_id ?? undefined} value={customCategoryId} onChange={setCustomCategoryId} required /></> : <ActivityCatalogSelector workspaceId={workspace.id} currentId={activity.activity_master_id ?? undefined} value={masterId} onChange={setMasterId} required />}{shared ? <MemberSelect label="Organizador" value={organizerId} members={members} onChange={setOrganizerId} required /> : null}<label>Inicio<input name="starts_at" type="datetime-local" required defaultValue={isoToLocalInput(activity.starts_at, timeZone)} /></label><label>Fin<input name="ends_at" type="datetime-local" required defaultValue={isoToLocalInput(activity.ends_at, timeZone)} /></label>{shared ? <ParticipantChecks members={members} selected={selected} onChange={setSelected} /> : null}{error ? <p role="alert">{error}</p> : null}<button disabled={pending}>Guardar</button><button type="button" onClick={onClose}>Cancelar</button></form></dialog>; }
function ScopeDialog({ action, shared, onClose, onConfirm }: { action: "DELETE" | "LEAVE"; shared: boolean; onClose: () => void; onConfirm: (scope: ActivityMutationScope) => void }) { return <dialog open><h2>{action === "LEAVE" ? "Retirarme de la Actividad" : shared ? "Cancelar Actividad" : "Eliminar Actividad"}</h2>{action === "LEAVE" ? <p>Solo se retirará de tu calendario.</p> : null}<button onClick={() => onConfirm("THIS")}>Solo esta</button><button onClick={() => onConfirm("THIS_AND_FUTURE")}>Esta y todas las futuras</button><button onClick={onClose}>Volver</button></dialog>; }
