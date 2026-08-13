import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import {
  createPlanningTask, createPlanningTasksBulk, deletePlanningTask, deletePlanningTasksBulk,
  listAllMasterTasks, listPlanningTasks, updatePlanningTask
} from "../../api/planningTaskApi";
import { queryKeys } from "../../api/queryKeys";
import type { PlanningTask, PlanningTaskListParams, PlanningTaskStatus } from "../../types/planningTask";
import { formatShortCalendarDate } from "../../utils/localizedDate";

const weekdays = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"] as const;
const statusLabels: Record<PlanningTaskStatus, string> = { PROGRAMADA: "Programada", PENDIENTE: "Pendiente", COMPLETADA: "Completada", NO_REALIZADA: "No realizada" };
type Mode = "single" | "bulk";

function messageFor(error: unknown): string {
  return axios.isAxiosError(error) && error.response?.status === 409
    ? "Ya existe esa tarea para una de las fechas seleccionadas o cambió desde la última carga."
    : "No pudimos completar la operación. Intenta nuevamente.";
}

export function PlanningTasksPage() {
  const client = useQueryClient();
  const [mode, setMode] = useState<Mode>("single");
  const [masterTaskId, setMasterTaskId] = useState("");
  const [plannedDate, setPlannedDate] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [pattern, setPattern] = useState<"DAILY" | "WEEKLY">("DAILY");
  const [selectedWeekdays, setSelectedWeekdays] = useState<number[]>([]);
  const [params, setParams] = useState<PlanningTaskListParams>({ page: 1, page_size: 25 });
  const [selected, setSelected] = useState<Record<string, number>>({});
  const [editing, setEditing] = useState<{ id: string; date: string; lockVersion: number } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const masters = useQuery({ queryKey: queryKeys.masterTasks, queryFn: listAllMasterTasks });
  const tasks = useQuery({ queryKey: queryKeys.planningTasks(params), queryFn: () => listPlanningTasks(params) });
  const categories = useMemo(() => Array.from(new Map((masters.data ?? []).map((item) => [item.category.id, item.category])).values()), [masters.data]);

  async function refreshRelated() {
    await Promise.all([
      client.invalidateQueries({ queryKey: queryKeys.planningTasksRoot }),
      client.invalidateQueries({ queryKey: queryKeys.home }),
      client.invalidateQueries({ queryKey: queryKeys.review })
    ]);
  }

  const create = useMutation({
    mutationFn: async () => {
      if (mode === "single") await createPlanningTask({ master_task_id: masterTaskId, planned_date: plannedDate });
      else await createPlanningTasksBulk({ master_task_id: masterTaskId, start_date: startDate, end_date: endDate, pattern, ...(pattern === "WEEKLY" ? { weekdays: selectedWeekdays } : {}) });
    },
    onSuccess: async () => { setError(null); setNotice("Tareas creadas."); setPlannedDate(""); await refreshRelated(); },
    onError: (caught) => { setNotice(null); setError(messageFor(caught)); }
  });
  const update = useMutation({ mutationFn: () => updatePlanningTask(editing!.id, { planned_date: editing!.date, lock_version: editing!.lockVersion }), onSuccess: async () => { setEditing(null); setError(null); setNotice("Fecha actualizada."); await refreshRelated(); }, onError: async (caught) => { setEditing(null); setError(messageFor(caught)); await client.invalidateQueries({ queryKey: queryKeys.planningTasksRoot }); } });
  const removeOne = useMutation({ mutationFn: (task: PlanningTask) => deletePlanningTask(task.id, task.lock_version), onSuccess: async () => { setNotice("Tarea eliminada."); setError(null); await refreshRelated(); }, onError: async (caught) => { setSelected({}); setError(messageFor(caught)); await client.invalidateQueries({ queryKey: queryKeys.planningTasksRoot }); } });
  const removeMany = useMutation({ mutationFn: () => deletePlanningTasksBulk(Object.entries(selected).map(([id, lock_version]) => ({ id, lock_version }))), onSuccess: async () => { setSelected({}); setNotice("Tareas seleccionadas eliminadas."); setError(null); await refreshRelated(); }, onError: async (caught) => { setSelected({}); setError(messageFor(caught)); await client.invalidateQueries({ queryKey: queryKeys.planningTasksRoot }); } });

  function submitCreation(event: React.FormEvent) {
    event.preventDefault();
    if (!masterTaskId || (mode === "single" && !plannedDate) || (mode === "bulk" && (!startDate || !endDate))) return setError("Completa los campos requeridos.");
    if (mode === "bulk" && startDate > endDate) return setError("La fecha inicial no puede ser posterior a la final.");
    if (mode === "bulk" && pattern === "WEEKLY" && selectedWeekdays.length === 0) return setError("Selecciona al menos un día de la semana.");
    setError(null); create.mutate();
  }

  const eligible = tasks.data?.items.filter((task) => task.status === "PROGRAMADA") ?? [];
  const allVisibleSelected = eligible.length > 0 && eligible.every((task) => selected[task.id] !== undefined);
  return <section className="planning-tasks-page">
    <header><p className="eyebrow">Planificación</p><h1>Planificación · Tareas</h1></header>
    <section className="planning-create" aria-labelledby="task-create-title"><h2 id="task-create-title">Crear tareas</h2>
      {masters.isPending ? <p role="status">Cargando tareas configuradas…</p> : masters.isError ? <div role="alert"><p>No pudimos cargar las tareas configuradas.</p><button type="button" className="secondary-button" onClick={() => void masters.refetch()}>Reintentar</button></div> : masters.data.length === 0 ? <p>Aún no hay tareas configuradas en Tablas &gt; Tareas.</p> :
      <form onSubmit={submitCreation}>
        <label>Tarea<select value={masterTaskId} onChange={(event) => setMasterTaskId(event.target.value)} required><option value="">Selecciona una tarea</option>{masters.data.map((item) => <option key={item.id} value={item.id}>{item.name} — {item.category.name}</option>)}</select></label>
        <label>Tipo de creación<select value={mode} onChange={(event) => setMode(event.target.value as Mode)}><option value="single">Puntual</option><option value="bulk">Repetida</option></select></label>
        {mode === "single" ? <label>Fecha<input type="date" required value={plannedDate} onChange={(event) => setPlannedDate(event.target.value)} /></label> : <>
          <label>Fecha inicial<input type="date" required value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label><label>Fecha final<input type="date" required value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label>
          <label>Patrón<select value={pattern} onChange={(event) => setPattern(event.target.value as "DAILY" | "WEEKLY")}><option value="DAILY">Todos los días</option><option value="WEEKLY">Días específicos de la semana</option></select></label>
          {pattern === "WEEKLY" ? <fieldset className="planning-weekdays"><legend>Días de la semana</legend>{weekdays.map((day, index) => <label key={day}><input type="checkbox" checked={selectedWeekdays.includes(index)} onChange={() => setSelectedWeekdays((current) => current.includes(index) ? current.filter((value) => value !== index) : [...current, index].sort())} />{day}</label>)}</fieldset> : null}
          {startDate && endDate ? <p className="planning-summary">Se crearán tareas entre {formatShortCalendarDate(startDate)} y {formatShortCalendarDate(endDate)}{pattern === "WEEKLY" && selectedWeekdays.length ? ` los ${selectedWeekdays.map((day) => weekdays[day].toLowerCase()).join(", ")}` : " todos los días"}.</p> : null}
        </>}
        <button className="primary-button" disabled={create.isPending} type="submit">{create.isPending ? "Creando…" : "Crear"}</button>
      </form>}
    </section>

    <section className="planning-register" aria-labelledby="task-register-title"><h2 id="task-register-title">Tareas planificadas</h2>
      <div className="planning-filters">
        <label>Desde<input type="date" value={params.planned_from ?? ""} onChange={(e) => setParams({ ...params, page: 1, planned_from: e.target.value || undefined })} /></label><label>Hasta<input type="date" value={params.planned_to ?? ""} onChange={(e) => setParams({ ...params, page: 1, planned_to: e.target.value || undefined })} /></label>
        <label>Tarea<select value={params.master_task_id ?? ""} onChange={(e) => setParams({ ...params, page: 1, master_task_id: e.target.value || undefined })}><option value="">Todas</option>{(masters.data ?? []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Categoría<select value={params.category_id ?? ""} onChange={(e) => setParams({ ...params, page: 1, category_id: e.target.value || undefined })}><option value="">Todas</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Estado<select value={params.status ?? ""} onChange={(e) => setParams({ ...params, page: 1, status: (e.target.value || undefined) as PlanningTaskStatus | undefined })}><option value="">Todos</option>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      </div>
      {error ? <p className="review-notice review-notice--error" role="alert">{error}</p> : null}{notice ? <p className="review-notice review-notice--success" role="status">{notice}</p> : null}
      <div className="planning-selection"><span>{Object.keys(selected).length} seleccionadas</span><button className="secondary-button" disabled={!Object.keys(selected).length || removeMany.isPending} type="button" onClick={() => window.confirm(`¿Eliminar ${Object.keys(selected).length} tareas programadas?`) && removeMany.mutate()}>Eliminar seleccionadas</button></div>
      {tasks.isPending ? <div className="planning-loading" role="status">Cargando tareas…</div> : tasks.isError ? <div role="alert"><p>No pudimos cargar las tareas.</p><button className="secondary-button" type="button" onClick={() => void tasks.refetch()}>Reintentar</button></div> : tasks.data.items.length === 0 ? <p className="review-empty">No hay tareas para los filtros seleccionados.</p> : <div className="planning-table" role="table" aria-label="Registro de tareas planificadas">
        <div className="planning-row planning-row--head" role="row"><span role="columnheader"><input aria-label="Seleccionar todas las tareas programadas visibles" type="checkbox" checked={allVisibleSelected} onChange={() => setSelected(allVisibleSelected ? {} : Object.fromEntries(eligible.map((task) => [task.id, task.lock_version])))} /></span><span role="columnheader">Fecha</span><span role="columnheader">Tarea</span><span role="columnheader">Categoría</span><span role="columnheader">Estado</span><span role="columnheader">Acciones</span></div>
        {tasks.data.items.map((task) => <div className="planning-row" role="row" key={task.id}><span role="cell"><input aria-label={`Seleccionar ${task.master_task.name}`} type="checkbox" disabled={task.status !== "PROGRAMADA"} checked={selected[task.id] !== undefined} onChange={() => setSelected((current) => current[task.id] !== undefined ? Object.fromEntries(Object.entries(current).filter(([id]) => id !== task.id)) : { ...current, [task.id]: task.lock_version })} /></span><span role="cell">{editing?.id === task.id ? <input aria-label={`Nueva fecha de ${task.master_task.name}`} type="date" value={editing.date} onChange={(e) => setEditing({ ...editing, date: e.target.value })} /> : formatShortCalendarDate(task.planned_date)}</span><strong role="cell">{task.master_task.name}</strong><span role="cell">{task.master_task.category.name}</span><span role="cell" className={`task-status task-status--${task.status.toLowerCase()}`}>{statusLabels[task.status]}</span><span role="cell" className="planning-actions">{task.status === "PROGRAMADA" ? editing?.id === task.id ? <><button aria-label={`Guardar fecha de ${task.master_task.name}`} type="button" onClick={() => update.mutate()}>✓</button><button aria-label={`Cancelar edición de ${task.master_task.name}`} type="button" onClick={() => setEditing(null)}>×</button></> : <><button aria-label={`Editar fecha de ${task.master_task.name}`} type="button" onClick={() => setEditing({ id: task.id, date: task.planned_date, lockVersion: task.lock_version })}>✎</button><button aria-label={`Eliminar ${task.master_task.name}`} type="button" onClick={() => window.confirm("¿Eliminar esta tarea programada?") && removeOne.mutate(task)}>⌫</button></> : null}</span></div>)}
      </div>}
      {tasks.data ? <div className="planning-pagination"><span>Página {tasks.data.page} de {Math.max(1, tasks.data.total_pages)}</span><label>Por página<select value={params.page_size} onChange={(e) => setParams({ ...params, page: 1, page_size: Number(e.target.value) })}>{[25,50,100].map((size) => <option key={size}>{size}</option>)}</select></label><button type="button" disabled={params.page <= 1} onClick={() => setParams({ ...params, page: params.page - 1 })}>Anterior</button><button type="button" disabled={params.page >= tasks.data.total_pages} onClick={() => setParams({ ...params, page: params.page + 1 })}>Siguiente</button></div> : null}
    </section>
  </section>;
}
