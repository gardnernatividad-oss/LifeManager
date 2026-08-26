import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { queryKeys } from "../../api/queryKeys";
import { createV2RecurringTasks, createV2Task, deleteV2Task, listV2Tasks, resolveV2Task, updateV2Task } from "../../api/v2TaskApi";
import { listWorkspaceMembers } from "../../api/workspaceApi";
import { TaskCatalogSelector } from "../../components/common/V2CatalogSelector";
import { useAuth } from "../../hooks/useAuth";
import type { V2RecurringTaskCreateResponse, V2Task, V2TaskFilters, V2TaskRecurrencePattern, V2TaskResult, V2TaskState } from "../../types/v2Task";
import { formatShortCalendarDate } from "../../utils/localizedDate";
import { recurrenceOccurrenceCount } from "../../utils/taskRecurrence";
import type { WorkspaceSummary } from "../../types/auth";

const labels: Record<V2TaskState, string> = { PROGRAMADA: "Programada", PENDIENTE: "Pendiente", COMPLETADA: "Completada", NO_REALIZADA: "No realizada" };
function messageFor(error: unknown): string {
  if (axios.isAxiosError(error) && error.response?.status === 409) return "La tarea cambió o no admite esta acción. Actualiza e inténtalo nuevamente.";
  if (axios.isAxiosError(error) && error.response?.status === 403) return "No tienes permiso para realizar esta acción.";
  if (axios.isAxiosError(error) && error.response?.status === 404) return "La tarea o una de sus referencias ya no está disponible.";
  return "No pudimos completar la operación. Intenta nuevamente.";
}
type Editing = { task: V2Task; masterTaskId: string; plannedDate: string; responsibleUserId: string };
type CreationMode = "ONCE" | "RECURRING";
const weekdays = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
const maxRecurringOccurrences = 1000;

export function PlanningTasksPage() {
  const { workspace, user } = useAuth();
  if (!workspace || !user) return <section><h1>Planificación · Tareas</h1><p>Selecciona un espacio de trabajo.</p></section>;
  return <WorkspaceTasks key={workspace.id} workspace={workspace} />;
}

function WorkspaceTasks({ workspace }: { workspace: WorkspaceSummary }) {
  const queryClient = useQueryClient();
  const workspaceId = workspace.id;
  const shared = workspace.kind === "SHARED";
  const [masterTaskId, setMasterTaskId] = useState("");
  const [plannedDate, setPlannedDate] = useState("");
  const [responsibleUserId, setResponsibleUserId] = useState("");
  const [creationMode, setCreationMode] = useState<CreationMode>("ONCE");
  const [recurrencePattern, setRecurrencePattern] = useState<V2TaskRecurrencePattern>("DAILY");
  const [dateFrom, setDateFrom] = useState("");
  const [dateUntil, setDateUntil] = useState("");
  const [selectedWeekdays, setSelectedWeekdays] = useState<number[]>([]);
  const [monthDaysInput, setMonthDaysInput] = useState("");
  const [filters, setFilters] = useState<V2TaskFilters>({ page: 1, page_size: 25 });
  const [editing, setEditing] = useState<Editing | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const members = useQuery({ queryKey: queryKeys.workspaceMembers(workspaceId), queryFn: () => listWorkspaceMembers(workspaceId), enabled: Boolean(workspaceId && shared) });
  const tasks = useQuery({ queryKey: queryKeys.v2Tasks(workspaceId, filters), queryFn: () => listV2Tasks(workspaceId, filters), enabled: Boolean(workspaceId) });
  const refresh = () => queryClient.invalidateQueries({ queryKey: queryKeys.v2TasksRoot(workspaceId) });
  const monthDayTokens = monthDaysInput.split(",").map((value) => value.trim()).filter(Boolean);
  const parsedMonthDays = monthDayTokens.map(Number);
  const monthDays = [...new Set(parsedMonthDays)];
  const invalidMonthDays = monthDayTokens.length === 0 || parsedMonthDays.some((value) => !Number.isInteger(value) || value < 1 || value > 31) || monthDays.length !== parsedMonthDays.length;
  const recurrence = { pattern: recurrencePattern, date_from: dateFrom, date_until: dateUntil, ...(recurrencePattern === "WEEKLY" ? { weekdays: selectedWeekdays } : {}), ...(recurrencePattern === "MONTHLY" ? { month_days: monthDays } : {}) };
  const occurrenceCount = recurrenceOccurrenceCount(recurrence);
  const create = useMutation<V2Task | V2RecurringTaskCreateResponse>({ mutationFn: () => creationMode === "ONCE"
    ? createV2Task(workspaceId, { master_task_id: masterTaskId, planned_date: plannedDate, ...(shared ? { responsible_user_id: responsibleUserId } : {}) })
    : createV2RecurringTasks(workspaceId, { master_task_id: masterTaskId, ...(shared ? { responsible_user_id: responsibleUserId } : {}), recurrence }), onSuccess: async (created) => { setMasterTaskId(""); setPlannedDate(""); setResponsibleUserId(""); setDateFrom(""); setDateUntil(""); setSelectedWeekdays([]); setMonthDaysInput(""); setError(null); setNotice("created_count" in created ? `Se crearon ${created.created_count} tareas.` : "Tarea creada."); await refresh(); }, onError: (caught) => { setNotice(null); setError(messageFor(caught)); } });
  const update = useMutation({ mutationFn: () => updateV2Task(workspaceId, editing!.task.id, { master_task_id: editing!.masterTaskId, planned_date: editing!.plannedDate, responsible_user_id: editing!.responsibleUserId, lock_version: editing!.task.lock_version }), onSuccess: async () => { setEditing(null); setError(null); setNotice("Tarea actualizada."); await refresh(); }, onError: async (caught) => { setEditing(null); setNotice(null); setError(messageFor(caught)); await refresh(); } });
  const resolve = useMutation({ mutationFn: ({ task, result }: { task: V2Task; result: V2TaskResult }) => resolveV2Task(workspaceId, task.id, result, task.lock_version), onSuccess: async () => { setError(null); setNotice("Resultado guardado."); await refresh(); }, onError: async (caught) => { setNotice(null); setError(messageFor(caught)); await refresh(); } });
  const remove = useMutation({ mutationFn: (task: V2Task) => deleteV2Task(workspaceId, task.id, task.lock_version), onSuccess: async () => { setError(null); setNotice("Tarea eliminada."); await refresh(); }, onError: async (caught) => { setNotice(null); setError(messageFor(caught)); await refresh(); } });

  const activeMembers = members.data?.filter((member) => member.status === "ACTIVE") ?? [];
  return <section className="planning-tasks-page">
    <header><p className="eyebrow">Planificación</p><h1>Planificación · Tareas</h1></header>
    <section className="planning-create" aria-labelledby="create-v2-task"><h2 id="create-v2-task">Crear tarea</h2><form onSubmit={(event) => { event.preventDefault(); const invalidRecurrence = creationMode === "RECURRING" && (!dateFrom || !dateUntil || dateFrom > dateUntil || (recurrencePattern === "WEEKLY" && selectedWeekdays.length === 0) || (recurrencePattern === "MONTHLY" && invalidMonthDays) || occurrenceCount === 0 || occurrenceCount > maxRecurringOccurrences); if (!masterTaskId || (creationMode === "ONCE" && !plannedDate) || invalidRecurrence || (shared && !responsibleUserId)) { setError(occurrenceCount > maxRecurringOccurrences ? `La recurrencia supera el límite de ${maxRecurringOccurrences} tareas.` : "Completa correctamente los campos requeridos."); return; } create.mutate(); }}>
      <TaskCatalogSelector workspaceId={workspaceId} value={masterTaskId} onChange={setMasterTaskId} required />
      <label>Tipo<select aria-label="Tipo de creación" value={creationMode} onChange={(event) => setCreationMode(event.target.value as CreationMode)}><option value="ONCE">Una vez</option><option value="RECURRING">Repetir</option></select></label>
      {creationMode === "ONCE" ? <label>Fecha<input type="date" value={plannedDate} onChange={(event) => setPlannedDate(event.target.value)} required /></label> : <fieldset className="task-recurrence-fields"><legend>Recurrencia finita</legend><label>Frecuencia<select aria-label="Frecuencia" value={recurrencePattern} onChange={(event) => { setRecurrencePattern(event.target.value as V2TaskRecurrencePattern); setSelectedWeekdays([]); setMonthDaysInput(""); }}><option value="DAILY">Diariamente</option><option value="WEEKLY">Semanalmente</option><option value="MONTHLY">Mensualmente</option></select></label><label>Desde<input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} required /></label><label>Hasta<input type="date" value={dateUntil} onChange={(event) => setDateUntil(event.target.value)} required /></label>{recurrencePattern === "WEEKLY" ? <fieldset><legend>Días de la semana</legend>{weekdays.map((label, index) => <label key={label}><input type="checkbox" checked={selectedWeekdays.includes(index)} onChange={(event) => setSelectedWeekdays(event.target.checked ? [...selectedWeekdays, index].sort((a, b) => a - b) : selectedWeekdays.filter((day) => day !== index))} />{label}</label>)}</fieldset> : null}{recurrencePattern === "MONTHLY" ? <><label>Días del mes<input aria-label="Días del mes" inputMode="numeric" placeholder="1, 15, 31" value={monthDaysInput} onChange={(event) => setMonthDaysInput(event.target.value)} /></label><p>Si el día no existe en un mes, se usará el último día de ese mes.</p></> : null}<p role="status">Se crearán {occurrenceCount} tareas.</p></fieldset>}
      {shared ? members.isPending ? <p role="status">Cargando responsables…</p> : members.isError ? <div role="alert">No pudimos cargar los responsables. <button type="button" onClick={() => void members.refetch()}>Reintentar</button></div> : <label>Responsable<select aria-label="Responsable" value={responsibleUserId} onChange={(event) => setResponsibleUserId(event.target.value)} required><option value="">Selecciona una persona</option>{activeMembers.map((member) => <option key={member.user_id} value={member.user_id}>{member.display_name}</option>)}</select></label> : null}
      <button className="primary-button" disabled={create.isPending} type="submit">{create.isPending ? "Creando…" : "Crear"}</button>
    </form></section>
    <section className="planning-register" aria-labelledby="v2-task-list"><h2 id="v2-task-list">Tareas planificadas</h2><div className="planning-filters">
      <label>Desde<input type="date" value={filters.planned_from ?? ""} onChange={(event) => setFilters({ ...filters, page: 1, planned_from: event.target.value || undefined })} /></label>
      <label>Hasta<input type="date" value={filters.planned_until ?? ""} onChange={(event) => setFilters({ ...filters, page: 1, planned_until: event.target.value || undefined })} /></label>
      {shared ? <label>Responsable<select value={filters.responsible_user_id ?? ""} onChange={(event) => setFilters({ ...filters, page: 1, responsible_user_id: event.target.value || undefined })}><option value="">Todos</option>{activeMembers.map((member) => <option key={member.user_id} value={member.user_id}>{member.display_name}</option>)}</select></label> : null}
      <label>Resultado<select value={filters.unresolved === true ? "unresolved" : filters.result ?? ""} onChange={(event) => { const value = event.target.value; setFilters({ ...filters, page: 1, unresolved: value === "unresolved" ? true : undefined, result: value === "COMPLETED" || value === "NOT_COMPLETED" ? value : undefined }); }}><option value="">Todos</option><option value="unresolved">Sin resolver</option><option value="COMPLETED">Completado</option><option value="NOT_COMPLETED">No realizado</option></select></label>
    </div>{error ? <p className="review-notice review-notice--error" role="alert">{error}</p> : null}{notice ? <p className="review-notice review-notice--success" role="status">{notice}</p> : null}
    {tasks.isPending ? <p role="status">Cargando tareas…</p> : tasks.isError ? <div role="alert">No pudimos cargar las tareas. <button type="button" onClick={() => void tasks.refetch()}>Reintentar</button></div> : tasks.data.items.length === 0 ? <p className="review-empty">No hay tareas para los filtros seleccionados.</p> : <div className="v2-task-list" role="table" aria-label="Tareas planificadas"><div className={`v2-task-row ${shared ? "" : "v2-task-row--personal"} v2-task-row--head`} role="row"><span>Fecha</span><span>Tarea</span>{shared ? <span>Responsable</span> : null}<span>Estado</span><span>Acciones</span></div>{tasks.data.items.map((task) => <article className={`v2-task-row ${shared ? "" : "v2-task-row--personal"}`} role="row" key={task.id}><span>{formatShortCalendarDate(task.planned_date)}</span><span><strong>{task.master_task_name}</strong><small>{task.category_name}</small></span>{shared ? <span>{task.responsible_display_name}</span> : null}<span className={`task-status task-status--${task.state.toLowerCase()}`}>{labels[task.state]}</span><span className="planning-actions">{task.can_edit ? <button type="button" aria-label={`Editar ${task.master_task_name}`} onClick={() => setEditing({ task, masterTaskId: task.master_task_id, plannedDate: task.planned_date, responsibleUserId: task.responsible_user_id })}>Editar</button> : null}{task.can_resolve ? <><button type="button" onClick={() => resolve.mutate({ task, result: "COMPLETED" })}>Completado</button><button type="button" onClick={() => resolve.mutate({ task, result: "NOT_COMPLETED" })}>No realizado</button></> : null}{task.can_delete ? <button type="button" aria-label={`Eliminar ${task.master_task_name}`} onClick={() => window.confirm("¿Eliminar esta tarea futura?") && remove.mutate(task)}>Eliminar</button> : null}</span></article>)}</div>}
    {tasks.data ? <div className="planning-pagination"><span>Página {tasks.data.page} de {Math.max(1, tasks.data.total_pages)}</span><label>Por página<select value={filters.page_size} onChange={(event) => setFilters({ ...filters, page: 1, page_size: Number(event.target.value) })}>{[25, 50, 100].map((size) => <option key={size}>{size}</option>)}</select></label><button type="button" disabled={filters.page <= 1} onClick={() => setFilters({ ...filters, page: filters.page - 1 })}>Anterior</button><button type="button" disabled={filters.page >= tasks.data.total_pages} onClick={() => setFilters({ ...filters, page: filters.page + 1 })}>Siguiente</button></div> : null}</section>
    {editing ? <div className="modal-backdrop"><section className="modal-card" role="dialog" aria-modal="true" aria-labelledby="edit-task-title"><h2 id="edit-task-title">Editar tarea</h2><form onSubmit={(event) => { event.preventDefault(); update.mutate(); }}><TaskCatalogSelector workspaceId={workspaceId} currentId={editing.task.master_task_id} value={editing.masterTaskId} onChange={(value) => setEditing({ ...editing, masterTaskId: value })} required /><label>Fecha<input type="date" value={editing.plannedDate} onChange={(event) => setEditing({ ...editing, plannedDate: event.target.value })} required /></label>{shared ? <label>Responsable<select value={editing.responsibleUserId} onChange={(event) => setEditing({ ...editing, responsibleUserId: event.target.value })}>{activeMembers.map((member) => <option key={member.user_id} value={member.user_id}>{member.display_name}</option>)}</select></label> : null}<div className="planning-actions"><button className="primary-button" type="submit">Guardar</button><button className="secondary-button" type="button" onClick={() => setEditing(null)}>Cancelar</button></div></form></section></div> : null}
  </section>;
}
