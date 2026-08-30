import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { queryKeys } from "../../api/queryKeys";
import { correctV2TaskResult, createV2RecurringTasks, createV2Task, deleteV2Task, listV2Tasks, resolveV2Task, updateV2Task } from "../../api/v2TaskApi";
import { listWorkspaceMembers } from "../../api/workspaceApi";
import { CategorySelector, TaskCatalogSelector } from "../../components/common/V2CatalogSelector";
import { ColumnPreferences, useColumnPreferences } from "../../components/common/ColumnPreferences";
import { useAuth } from "../../hooks/useAuth";
import type { V2RecurringTaskCreateResponse, V2Task, V2TaskFilters, V2TaskMutationScope, V2TaskRecurrencePattern, V2TaskResult, V2TaskState } from "../../types/v2Task";
import { formatShortCalendarDate } from "../../utils/localizedDate";
import { recurrenceOccurrenceCount } from "../../utils/taskRecurrence";
import type { WorkspaceSummary } from "../../types/auth";

const labels: Record<V2TaskState, string> = { PROGRAMADA: "Programada", PENDIENTE: "Pendiente", COMPLETADA: "Completada", NO_REALIZADA: "No realizada" };
const taskDisplayName = (task: V2Task): string => task.task_name ?? task.master_task_name ?? task.custom_name ?? "";
const isCustomTask = (task: V2Task): boolean => task.source === "CUSTOM" || task.master_task_id === null;
function messageFor(error: unknown): string {
  if (axios.isAxiosError(error) && error.response?.status === 409) return "La tarea cambió o no admite esta acción. Actualiza e inténtalo nuevamente.";
  if (axios.isAxiosError(error) && error.response?.status === 403) return "No tienes permiso para realizar esta acción.";
  if (axios.isAxiosError(error) && error.response?.status === 404) return "La tarea o una de sus referencias ya no está disponible.";
  return "No pudimos completar la operación. Intenta nuevamente.";
}
type Editing = { task: V2Task; masterTaskId: string; customName: string; customCategoryId: string; plannedDate: string; responsibleUserId: string; scope: V2TaskMutationScope };
type ScopeAction = { task: V2Task; action: "EDIT" | "DELETE" };
type CreationMode = "ONCE" | "RECURRING";
const weekdays = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
const maxRecurringOccurrences = 1000;

export function PlanningTasksPage() {
  const { workspace, user } = useAuth();
  if (!workspace || !user) return <section><h1>Planificación · Tareas</h1><p>Selecciona un espacio de trabajo.</p></section>;
  return <WorkspaceTasks key={workspace.id} workspace={workspace} userId={user.id} />;
}

function WorkspaceTasks({ workspace, userId }: { workspace: WorkspaceSummary; userId: string }) {
  const queryClient = useQueryClient();
  const workspaceId = workspace.id;
  const shared = workspace.kind === "SHARED";
  const taskColumns = [
    { key: "date", label: "Fecha" },
    { key: "task", label: "Tarea" },
    { key: "responsible", label: "Responsable", defaultVisible: shared },
    { key: "state", label: "Estado" },
  ];
  const columnPreferences = useColumnPreferences(userId, "planning-tasks", taskColumns);
  const hiddenColumns = taskColumns.filter((column) => !columnPreferences.visible.includes(column.key)).map((column) => column.key).join(" ");
  const [masterTaskId, setMasterTaskId] = useState("");
  const [customName, setCustomName] = useState("");
  const [customCategoryId, setCustomCategoryId] = useState("");
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
  const [scopeAction, setScopeAction] = useState<ScopeAction | null>(null);
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
  const sourcePayload = masterTaskId === "__custom__" ? { custom_name: customName, custom_category_id: customCategoryId } : { master_task_id: masterTaskId };
  const create = useMutation<V2Task | V2RecurringTaskCreateResponse>({ mutationFn: () => creationMode === "ONCE"
    ? createV2Task(workspaceId, { ...sourcePayload, planned_date: plannedDate, ...(shared ? { responsible_user_id: responsibleUserId } : {}) })
    : createV2RecurringTasks(workspaceId, { ...sourcePayload, ...(shared ? { responsible_user_id: responsibleUserId } : {}), recurrence }), onSuccess: async (created) => { setMasterTaskId(""); setCustomName(""); setCustomCategoryId(""); setPlannedDate(""); setResponsibleUserId(""); setDateFrom(""); setDateUntil(""); setSelectedWeekdays([]); setMonthDaysInput(""); setError(null); setNotice("created_count" in created ? `Se crearon ${created.created_count} tareas.` : "Tarea creada."); await refresh(); }, onError: (caught) => { setNotice(null); setError(messageFor(caught)); } });
  const update = useMutation({ mutationFn: () => updateV2Task(workspaceId, editing!.task.id, { ...(isCustomTask(editing!.task) ? { custom_name: editing!.customName, custom_category_id: editing!.customCategoryId } : { master_task_id: editing!.masterTaskId }), ...(editing!.scope === "THIS" ? { planned_date: editing!.plannedDate } : {}), responsible_user_id: editing!.responsibleUserId, lock_version: editing!.task.lock_version, scope: editing!.scope }), onSuccess: async () => { setEditing(null); setError(null); setNotice("Tarea actualizada."); await refresh(); }, onError: async (caught) => { setEditing(null); setNotice(null); setError(messageFor(caught)); await refresh(); } });
  const resolve = useMutation({ mutationFn: ({ task, result }: { task: V2Task; result: V2TaskResult }) => resolveV2Task(workspaceId, task.id, result, task.lock_version), onSuccess: async () => { setError(null); setNotice("Resultado guardado."); await refresh(); }, onError: async (caught) => { setNotice(null); setError(messageFor(caught)); await refresh(); } });
  const correct = useMutation({ mutationFn: (task: V2Task) => correctV2TaskResult(workspaceId, task.id, task.result === "COMPLETED" ? "NOT_COMPLETED" : "COMPLETED", task.lock_version), onSuccess: async () => { setError(null); setNotice("Resultado corregido."); await refresh(); }, onError: async (caught) => { setNotice(null); setError(messageFor(caught)); await refresh(); } });
  const remove = useMutation({ mutationFn: ({ task, scope }: { task: V2Task; scope: V2TaskMutationScope }) => deleteV2Task(workspaceId, task.id, task.lock_version, scope), onSuccess: async () => { setScopeAction(null); setError(null); setNotice("Tarea eliminada."); await refresh(); }, onError: async (caught) => { setScopeAction(null); setNotice(null); setError(messageFor(caught)); await refresh(); } });
  const beginEdit = (task: V2Task, scope: V2TaskMutationScope) => { setScopeAction(null); setEditing({ task, masterTaskId: task.master_task_id ?? "", customName: task.custom_name ?? task.task_name ?? "", customCategoryId: task.custom_category_id ?? "", plannedDate: task.planned_date, responsibleUserId: task.responsible_user_id, scope }); };
  const beginDelete = (task: V2Task, scope: V2TaskMutationScope) => { if (window.confirm(scope === "THIS" ? "¿Eliminar solo esta tarea futura?" : "¿Eliminar esta tarea y todas las futuras de la recurrencia?")) remove.mutate({ task, scope }); };

  const activeMembers = members.data?.filter((member) => member.status === "ACTIVE") ?? [];
  return <section className="planning-tasks-page">
    <header><p className="eyebrow">Planificación</p><h1>Planificación · Tareas</h1></header>
    <section className="planning-create" aria-labelledby="create-v2-task"><h2 id="create-v2-task">Crear tarea</h2><form onSubmit={(event) => { event.preventDefault(); const invalidRecurrence = creationMode === "RECURRING" && (!dateFrom || !dateUntil || dateFrom > dateUntil || (recurrencePattern === "WEEKLY" && selectedWeekdays.length === 0) || (recurrencePattern === "MONTHLY" && invalidMonthDays) || occurrenceCount === 0 || occurrenceCount > maxRecurringOccurrences); const invalidCustom = masterTaskId === "__custom__" && (!customName.trim() || !customCategoryId); if (!masterTaskId || invalidCustom || (creationMode === "ONCE" && !plannedDate) || invalidRecurrence || (shared && !responsibleUserId)) { setError(occurrenceCount > maxRecurringOccurrences ? `La recurrencia supera el límite de ${maxRecurringOccurrences} tareas.` : "Completa correctamente los campos requeridos."); return; } create.mutate(); }}>
      <TaskCatalogSelector workspaceId={workspaceId} value={masterTaskId} onChange={(value) => { setMasterTaskId(value); setCustomName(""); setCustomCategoryId(""); }} includeCustomOption required />
      {masterTaskId === "__custom__" ? <><label>Nombre<input value={customName} maxLength={150} onChange={(event) => setCustomName(event.target.value)} required /></label><CategorySelector workspaceId={workspaceId} value={customCategoryId} onChange={setCustomCategoryId} required /></> : null}
      <label>Tipo<select aria-label="Tipo de creación" value={creationMode} onChange={(event) => setCreationMode(event.target.value as CreationMode)}><option value="ONCE">Una vez</option><option value="RECURRING">Repetir</option></select></label>
      {creationMode === "ONCE" ? <label>Fecha<input type="date" value={plannedDate} onChange={(event) => setPlannedDate(event.target.value)} required /></label> : <fieldset className="task-recurrence-fields"><legend>Recurrencia finita</legend><label>Frecuencia<select aria-label="Frecuencia" value={recurrencePattern} onChange={(event) => { setRecurrencePattern(event.target.value as V2TaskRecurrencePattern); setSelectedWeekdays([]); setMonthDaysInput(""); }}><option value="DAILY">Diariamente</option><option value="WEEKLY">Semanalmente</option><option value="MONTHLY">Mensualmente</option></select></label><label>Desde<input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} required /></label><label>Hasta<input type="date" value={dateUntil} onChange={(event) => setDateUntil(event.target.value)} required /></label>{recurrencePattern === "WEEKLY" ? <fieldset><legend>Días de la semana</legend>{weekdays.map((label, index) => <label key={label}><input type="checkbox" checked={selectedWeekdays.includes(index)} onChange={(event) => setSelectedWeekdays(event.target.checked ? [...selectedWeekdays, index].sort((a, b) => a - b) : selectedWeekdays.filter((day) => day !== index))} />{label}</label>)}</fieldset> : null}{recurrencePattern === "MONTHLY" ? <><label>Días del mes<input aria-label="Días del mes" inputMode="numeric" placeholder="1, 15, 31" value={monthDaysInput} onChange={(event) => setMonthDaysInput(event.target.value)} /></label><p>Si el día no existe en un mes, se usará el último día de ese mes.</p></> : null}<p role="status">Se crearán {occurrenceCount} tareas.</p></fieldset>}
      {shared ? members.isPending ? <p role="status">Cargando responsables…</p> : members.isError ? <div role="alert">No pudimos cargar los responsables. <button type="button" onClick={() => void members.refetch()}>Reintentar</button></div> : <label>Responsable<select aria-label="Responsable" value={responsibleUserId} onChange={(event) => setResponsibleUserId(event.target.value)} required><option value="">Selecciona una persona</option>{activeMembers.map((member) => <option key={member.user_id} value={member.user_id}>{member.display_name}</option>)}</select></label> : null}
      <button className="primary-button" disabled={create.isPending} type="submit">{create.isPending ? "Creando…" : "Crear"}</button>
    </form></section>
    <section className="planning-register" aria-labelledby="v2-task-list" data-hidden-columns={hiddenColumns}><h2 id="v2-task-list">Tareas planificadas</h2><ColumnPreferences columns={taskColumns} visible={columnPreferences.visible} onChange={columnPreferences.setVisible} /><div className="planning-filters">
      <label>Desde<input type="date" value={filters.planned_from ?? ""} onChange={(event) => setFilters({ ...filters, page: 1, planned_from: event.target.value || undefined })} /></label>
      <label>Hasta<input type="date" value={filters.planned_until ?? ""} onChange={(event) => setFilters({ ...filters, page: 1, planned_until: event.target.value || undefined })} /></label>
      {shared ? <label>Responsable<select value={filters.responsible_user_id ?? ""} onChange={(event) => setFilters({ ...filters, page: 1, responsible_user_id: event.target.value || undefined })}><option value="">Todos</option>{activeMembers.map((member) => <option key={member.user_id} value={member.user_id}>{member.display_name}</option>)}</select></label> : null}
      <TaskCatalogSelector workspaceId={workspaceId} value={filters.custom ? "__custom__" : filters.master_task_id ?? ""} onChange={(value) => setFilters({ ...filters, page: 1, master_task_id: value && value !== "__custom__" ? value : undefined, custom: value === "__custom__" ? true : undefined })} includeCustomOption />
      <CategorySelector workspaceId={workspaceId} value={filters.category_id ?? ""} onChange={(value) => setFilters({ ...filters, page: 1, category_id: value || undefined })} />
      <label>Estado<select value={filters.state ?? ""} onChange={(event) => setFilters({ ...filters, page: 1, state: (event.target.value || undefined) as V2TaskState | undefined, result: undefined, unresolved: undefined })}><option value="">Todos</option><option value="PROGRAMADA">Programada</option><option value="PENDIENTE">Pendiente</option><option value="COMPLETADA">Completada</option><option value="NO_REALIZADA">No realizada</option></select></label>
      <label>Origen<select value={filters.generated === undefined ? "" : String(filters.generated)} onChange={(event) => setFilters({ ...filters, page: 1, generated: event.target.value === "" ? undefined : event.target.value === "true" })}><option value="">Todas</option><option value="false">Una vez</option><option value="true">Repetidas</option></select></label>
    </div>{error ? <p className="review-notice review-notice--error" role="alert">{error}</p> : null}{notice ? <p className="review-notice review-notice--success" role="status">{notice}</p> : null}
    {tasks.isPending ? <p role="status">Cargando tareas…</p> : tasks.isError ? <div role="alert">No pudimos cargar las tareas. <button type="button" onClick={() => void tasks.refetch()}>Reintentar</button></div> : tasks.data.items.length === 0 ? <p className="review-empty">No hay tareas para los filtros seleccionados.</p> : <div className="v2-task-list" role="table" aria-label="Tareas planificadas"><div className={`v2-task-row ${shared ? "" : "v2-task-row--personal"} v2-task-row--head`} role="row"><span>Fecha</span><span>Tarea</span>{shared ? <span>Responsable</span> : null}<span>Estado</span><span>Acciones</span></div>{tasks.data.items.map((task) => <article className={`v2-task-row ${shared ? "" : "v2-task-row--personal"}`} role="row" key={task.id}><span data-label="Fecha">{formatShortCalendarDate(task.planned_date)}</span><span data-label="Tarea"><strong>{taskDisplayName(task)}</strong><small>{task.category_name}{task.source === "CUSTOM" ? " · Otra tarea" : ""}{task.is_generated ? " · Repetida" : ""}</small></span>{shared ? <span data-label="Responsable">{task.responsible_display_name}</span> : null}<span data-label="Estado" className={`task-status task-status--${task.state.toLowerCase()}`}>{labels[task.state]}</span><span className="planning-actions" data-label="Acciones">{task.can_edit_this ? <button type="button" aria-label={`Editar ${taskDisplayName(task)}`} onClick={() => task.can_edit_future ? setScopeAction({ task, action: "EDIT" }) : beginEdit(task, "THIS")}>Editar</button> : null}{task.can_resolve ? <><button type="button" onClick={() => resolve.mutate({ task, result: "COMPLETED" })}>Completado</button><button type="button" onClick={() => resolve.mutate({ task, result: "NOT_COMPLETED" })}>No realizado</button></> : null}{task.can_correct_result ? <button type="button" onClick={() => correct.mutate(task)}>Corregir resultado</button> : null}{task.can_delete_this ? <button type="button" aria-label={`Eliminar ${taskDisplayName(task)}`} onClick={() => task.can_delete_future ? setScopeAction({ task, action: "DELETE" }) : beginDelete(task, "THIS")}>Eliminar</button> : null}</span></article>)}</div>}
    {tasks.data ? <div className="planning-pagination"><span>Página {tasks.data.page} de {Math.max(1, tasks.data.total_pages)}</span><label>Por página<select value={filters.page_size} onChange={(event) => setFilters({ ...filters, page: 1, page_size: Number(event.target.value) })}>{[25, 50, 100].map((size) => <option key={size}>{size}</option>)}</select></label><button type="button" disabled={filters.page <= 1} onClick={() => setFilters({ ...filters, page: filters.page - 1 })}>Anterior</button><button type="button" disabled={filters.page >= tasks.data.total_pages} onClick={() => setFilters({ ...filters, page: filters.page + 1 })}>Siguiente</button></div> : null}</section>
    {scopeAction ? <div className="modal-backdrop"><section className="modal-card" role="dialog" aria-modal="true" aria-labelledby="task-scope-title"><h2 id="task-scope-title">Elegir alcance</h2><p>{scopeAction.action === "EDIT" ? "¿Aplicar el cambio solo a esta tarea o también a todas las futuras de esta recurrencia?" : "¿Eliminar solo esta tarea o también todas las futuras de esta recurrencia?"}</p><p>Las tareas de hoy, anteriores o resueltas no cambiarán.</p><div className="dialog-actions"><button type="button" onClick={() => scopeAction.action === "EDIT" ? beginEdit(scopeAction.task, "THIS") : beginDelete(scopeAction.task, "THIS")}>Solo esta</button><button type="button" onClick={() => scopeAction.action === "EDIT" ? beginEdit(scopeAction.task, "THIS_AND_FUTURE") : beginDelete(scopeAction.task, "THIS_AND_FUTURE")}>Todas las futuras</button><button type="button" onClick={() => setScopeAction(null)}>Cancelar</button></div></section></div> : null}
    {editing ? <div className="modal-backdrop"><section className="modal-card" role="dialog" aria-modal="true" aria-labelledby="edit-task-title"><h2 id="edit-task-title">Editar tarea</h2>{editing.scope === "THIS_AND_FUTURE" ? <p>El cambio se aplicará a esta tarea y a las futuras no resueltas de la recurrencia.</p> : null}<form onSubmit={(event) => { event.preventDefault(); update.mutate(); }}>{!isCustomTask(editing.task) ? <TaskCatalogSelector workspaceId={workspaceId} currentId={editing.task.master_task_id ?? undefined} value={editing.masterTaskId} onChange={(value) => setEditing({ ...editing, masterTaskId: value })} required /> : <><label>Nombre<input value={editing.customName} maxLength={150} onChange={(event) => setEditing({ ...editing, customName: event.target.value })} required /></label><CategorySelector workspaceId={workspaceId} currentId={editing.task.custom_category_id ?? undefined} value={editing.customCategoryId} onChange={(value) => setEditing({ ...editing, customCategoryId: value })} required /></>}{editing.scope === "THIS" ? <label>Fecha<input type="date" value={editing.plannedDate} onChange={(event) => setEditing({ ...editing, plannedDate: event.target.value })} required /></label> : null}{shared ? <label>Responsable<select value={editing.responsibleUserId} onChange={(event) => setEditing({ ...editing, responsibleUserId: event.target.value })}>{activeMembers.map((member) => <option key={member.user_id} value={member.user_id}>{member.display_name}</option>)}</select></label> : null}<div className="planning-actions"><button className="primary-button" type="submit">Guardar</button><button className="secondary-button" type="button" onClick={() => setEditing(null)}>Cancelar</button></div></form></section></div> : null}
  </section>;
}
