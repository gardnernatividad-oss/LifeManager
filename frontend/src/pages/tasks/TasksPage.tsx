import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useSearchParams } from "react-router-dom";
import { z } from "zod";

import { listCategories } from "../../api/categoryApi";
import { listProjects } from "../../api/projectApi";
import { queryKeys } from "../../api/queryKeys";
import { cancelTask, completeTask, createTask, listTasks, markTaskNotCompleted, updateTask } from "../../api/taskApi";
import { useAuth } from "../../hooks/useAuth";
import { useWorkspaces } from "../../hooks/useWorkspaces";
import type { Task, TaskListParams, TaskOrderBy, TaskOutcome, TaskStatus, TaskWrite } from "../../types/task";
import { formatTaskDate, isoToLocalInput, localDateTimeToIso } from "../../utils/taskDateTime";

const statuses: TaskStatus[] = ["scheduled", "pending", "completed", "not_completed", "cancelled"];
const outcomes: TaskOutcome[] = ["completed", "not_completed", "cancelled"];
const orderFields: TaskOrderBy[] = ["scheduled_at", "created_at", "updated_at", "title"];
const statusLabels: Record<TaskStatus, string> = {
  scheduled: "Programada", pending: "Pendiente", completed: "Completada",
  not_completed: "No realizada", cancelled: "Cancelada"
};

const taskSchema = z.object({
  title: z.string().trim().min(1, "Ingresa un título.").max(255, "El título no puede superar 255 caracteres."),
  description: z.string(),
  scheduledAt: z.string().min(1, "Selecciona una fecha y hora."),
  categoryId: z.string(),
  projectId: z.string()
});
type TaskForm = z.infer<typeof taskSchema>;

function safeChoice<T extends string>(value: string | null, allowed: readonly T[], fallback: T | "" = ""): T | "" {
  return value && allowed.includes(value as T) ? value as T : fallback;
}

function positiveInt(value: string | null, fallback: number, max?: number) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= 1 && (!max || parsed <= max) ? parsed : fallback;
}

function safeUuid(value: string | null) {
  return value && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value) ? value : "";
}

function safeInstant(value: string | null) {
  return value && !Number.isNaN(Date.parse(value)) ? new Date(value).toISOString() : "";
}

function readFilters(params: URLSearchParams): TaskListParams {
  return {
    page: positiveInt(params.get("page"), 1), pageSize: positiveInt(params.get("page_size"), 20, 100),
    search: params.get("search") ?? "", status: safeChoice(params.get("status"), statuses),
    outcome: safeChoice(params.get("outcome"), outcomes), categoryId: safeUuid(params.get("category")),
    projectId: safeUuid(params.get("project")), scheduledFrom: safeInstant(params.get("scheduled_from")),
    scheduledTo: safeInstant(params.get("scheduled_to")),
    orderBy: safeChoice(params.get("order_by"), orderFields, "scheduled_at") as TaskOrderBy,
    orderDirection: params.get("order_direction") === "desc" ? "desc" : "asc"
  };
}

function TaskDialog({ task, timezone, categories, projects, optionsLoading, pending, error, onClose, onSave }: {
  task: Task | null; timezone: string; categories: { id: string; name: string; is_active: boolean }[];
  projects: { id: string; name: string; is_active: boolean }[]; optionsLoading: boolean; pending: boolean; error: string | null;
  onClose: () => void; onSave: (values: TaskForm) => Promise<void>;
}) {
  const { register, handleSubmit, formState: { errors } } = useForm<TaskForm>({
    resolver: zodResolver(taskSchema),
    defaultValues: {
      title: task?.title ?? "", description: task?.description ?? "",
      scheduledAt: task ? isoToLocalInput(task.scheduled_at, timezone) : "",
      categoryId: task?.category_id ?? "", projectId: task?.project_id ?? ""
    }
  });
  useEffect(() => {
    const listener = (event: KeyboardEvent) => { if (event.key === "Escape" && !pending) onClose(); };
    document.addEventListener("keydown", listener); return () => document.removeEventListener("keydown", listener);
  }, [onClose, pending]);
  return <div className="dialog-backdrop"><section className="task-dialog" role="dialog" aria-modal="true" aria-labelledby="task-dialog-title">
    <h2 id="task-dialog-title">{task ? "Editar tarea" : "Nueva tarea"}</h2>
    <form onSubmit={handleSubmit(onSave)} noValidate>
      <div className="form-field"><label htmlFor="task-title">Título</label><input id="task-title" autoFocus aria-invalid={!!errors.title} {...register("title")} />{errors.title && <span className="field-error">{errors.title.message}</span>}</div>
      <div className="form-field"><label htmlFor="task-description">Descripción <span className="optional-label">(opcional)</span></label><textarea id="task-description" rows={3} {...register("description")} /></div>
      <div className="form-field"><label htmlFor="task-scheduled">Fecha y hora ({timezone})</label><input id="task-scheduled" type="datetime-local" aria-invalid={!!errors.scheduledAt} {...register("scheduledAt")} />{errors.scheduledAt && <span className="field-error">{errors.scheduledAt.message}</span>}</div>
      <div className="task-form-grid">
        <div className="form-field"><label htmlFor="task-category">Categoría</label><select id="task-category" disabled={optionsLoading} {...register("categoryId")}><option value="">Sin categoría</option>{categories.map((item) => <option key={item.id} value={item.id} disabled={!item.is_active && item.id !== task?.category_id}>{item.name}{!item.is_active ? " (inactiva)" : ""}</option>)}</select></div>
        <div className="form-field"><label htmlFor="task-project">Proyecto</label><select id="task-project" disabled={optionsLoading} {...register("projectId")}><option value="">Sin proyecto</option>{projects.map((item) => <option key={item.id} value={item.id} disabled={!item.is_active && item.id !== task?.project_id}>{item.name}{!item.is_active ? " (inactivo)" : ""}</option>)}</select></div>
      </div>
      {optionsLoading && <span role="status">Cargando categorías y proyectos…</span>}
      {error && <div className="form-alert" role="alert">{error}</div>}
      <div className="dialog-actions"><button className="secondary-button" type="button" disabled={pending} onClick={onClose}>Cerrar</button><button className="primary-button" type="submit" disabled={pending}>{pending ? "Guardando…" : "Guardar tarea"}</button></div>
    </form>
  </section></div>;
}

export function TasksPage() {
  const { workspace } = useAuth(); const workspaces = useWorkspaces(); const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams(); const filters = useMemo(() => readFilters(searchParams), [searchParams]);
  const [searchText, setSearchText] = useState(filters.search); const [dialogTask, setDialogTask] = useState<Task | null | undefined>();
  const [formError, setFormError] = useState<string | null>(null); const [actionError, setActionError] = useState<string | null>(null);
  const workspaceId = workspace?.id ?? "";

  const tasksQuery = useQuery({ queryKey: queryKeys.tasks(workspaceId, filters), queryFn: () => listTasks(workspaceId, filters), enabled: !!workspaceId });
  const categoriesQuery = useQuery({ queryKey: queryKeys.categories(workspaceId, null), queryFn: () => listCategories(workspaceId, null), enabled: !!workspaceId });
  const projectsQuery = useQuery({ queryKey: queryKeys.projects(workspaceId, null), queryFn: () => listProjects(workspaceId, null), enabled: !!workspaceId });

  const setFilter = (key: string, value: string) => { const next = new URLSearchParams(searchParams); if (value) next.set(key, value); else next.delete(key); if (key !== "page") next.delete("page"); setSearchParams(next); };
  const invalidate = async () => Promise.all([
    queryClient.invalidateQueries({ queryKey: queryKeys.tasksForWorkspace(workspaceId) }),
    queryClient.invalidateQueries({ queryKey: queryKeys.dashboardSummary(workspaceId) }),
    queryClient.invalidateQueries({ queryKey: queryKeys.dashboardStatistics(workspaceId) })
  ]);
  const saveMutation = useMutation({
    mutationFn: (values: TaskForm) => {
      const payload: TaskWrite = { title: values.title.trim(), description: values.description.trim() || null, scheduled_at: localDateTimeToIso(values.scheduledAt, workspace!.timezone), category_id: values.categoryId || null, project_id: values.projectId || null };
      return dialogTask ? updateTask(workspaceId, dialogTask.id, payload) : createTask(workspaceId, payload);
    }, onSuccess: async () => { setFilter("page", ""); await invalidate(); setDialogTask(undefined); setFormError(null); },
    onError: (error) => setFormError(axios.isAxiosError(error) && error.response?.status === 409 ? "La tarea o una de sus asignaciones ya no puede modificarse." : axios.isAxiosError(error) && error.response?.status === 404 ? "La categoría, el proyecto o la tarea ya no está disponible." : error instanceof Error && error.message.startsWith("La hora seleccionada") ? error.message : "No pudimos guardar la tarea. Intenta nuevamente.")
  });
  const resolution = useMutation({
    mutationFn: ({ task, action }: { task: Task; action: TaskOutcome }) => action === "completed" ? completeTask(workspaceId, task.id) : action === "not_completed" ? markTaskNotCompleted(workspaceId, task.id) : cancelTask(workspaceId, task.id),
    onMutate: () => setActionError(null), onSuccess: async () => { setFilter("page", ""); await invalidate(); },
    onError: (error) => setActionError(axios.isAxiosError(error) && error.response?.status === 409 ? "Esta tarea ya fue resuelta y no puede cambiarse." : "No pudimos resolver la tarea. Intenta nuevamente.")
  });

  if (workspaces.isPending || (workspaces.data?.length && !workspace)) return <div className="task-list-skeleton" role="status" aria-label="Cargando tareas" />;
  if (!workspace) return <section className="tasks-empty"><h1>No hay un espacio de trabajo disponible</h1><p>Selecciona o crea un espacio para administrar tareas.</p></section>;
  const categories = categoriesQuery.data ?? []; const projects = projectsQuery.data ?? [];
  const categoryNames = new Map(categories.map((item) => [item.id, item.name])); const projectNames = new Map(projects.map((item) => [item.id, item.name]));
  const data = tasksQuery.data;

  return <div className="tasks-page">
    <header className="tasks-header"><div><p className="eyebrow">{workspace.name}</p><h1>Tareas</h1><p>Planifica acciones, encuentra lo pendiente y registra cada resultado.</p></div><button className="primary-button" type="button" onClick={() => { setFormError(null); setDialogTask(null); }}>Nueva tarea</button></header>
    <section className="task-toolbar" aria-label="Filtros de tareas">
      <form className="task-search" onSubmit={(event) => { event.preventDefault(); setFilter("search", searchText.trim()); }}><label htmlFor="task-search">Buscar por título</label><div><input id="task-search" value={searchText} onChange={(e) => setSearchText(e.target.value)} /><button className="secondary-button" type="submit">Buscar</button></div></form>
      <div className="task-filter-grid">
        <label>Estado<select aria-label="Estado" value={filters.status} onChange={(e) => setFilter("status", e.target.value)}><option value="">Todos</option>{statuses.map((value) => <option key={value} value={value}>{statusLabels[value]}</option>)}</select></label>
        <label>Resultado<select aria-label="Resultado" value={filters.outcome} onChange={(e) => setFilter("outcome", e.target.value)}><option value="">Todos</option>{outcomes.map((value) => <option key={value} value={value}>{statusLabels[value]}</option>)}</select></label>
        <label>Categoría<select aria-label="Filtrar por categoría" value={filters.categoryId} onChange={(e) => setFilter("category", e.target.value)}><option value="">Todas</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Proyecto<select aria-label="Filtrar por proyecto" value={filters.projectId} onChange={(e) => setFilter("project", e.target.value)}><option value="">Todos</option>{projects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Desde<input aria-label="Programada desde" type="datetime-local" value={filters.scheduledFrom ? isoToLocalInput(filters.scheduledFrom, workspace.timezone) : ""} onChange={(e) => setFilter("scheduled_from", e.target.value ? localDateTimeToIso(e.target.value, workspace.timezone) : "")} /></label>
        <label>Hasta<input aria-label="Programada hasta" type="datetime-local" value={filters.scheduledTo ? isoToLocalInput(filters.scheduledTo, workspace.timezone) : ""} onChange={(e) => setFilter("scheduled_to", e.target.value ? localDateTimeToIso(e.target.value, workspace.timezone) : "")} /></label>
        <label>Ordenar por<select aria-label="Ordenar por" value={filters.orderBy} onChange={(e) => setFilter("order_by", e.target.value)}><option value="scheduled_at">Programación</option><option value="created_at">Creación</option><option value="updated_at">Actualización</option><option value="title">Título</option></select></label>
        <label>Dirección<select aria-label="Dirección" value={filters.orderDirection} onChange={(e) => setFilter("order_direction", e.target.value)}><option value="asc">Ascendente</option><option value="desc">Descendente</option></select></label>
      </div><button className="text-button" type="button" onClick={() => { setSearchText(""); setSearchParams({}); }}>Limpiar filtros</button>
    </section>
    {actionError && <div className="form-alert" role="alert">{actionError}</div>}
    {tasksQuery.isPending && <div className="task-list-skeleton" role="status" aria-label="Cargando tareas" />}
    {tasksQuery.isError && <div className="dashboard-error" role="alert"><p>No pudimos cargar las tareas.</p><button className="secondary-button" type="button" onClick={() => void tasksQuery.refetch()}>Reintentar</button></div>}
    {data?.items.length === 0 && <section className="tasks-empty"><h2>{filters.search || filters.status || filters.outcome || filters.categoryId || filters.projectId || filters.scheduledFrom || filters.scheduledTo ? "No encontramos tareas con estos filtros." : "Aún no tienes tareas."}</h2>{!data.total && !filters.search && !filters.status && !filters.outcome && !filters.categoryId && !filters.projectId && !filters.scheduledFrom && !filters.scheduledTo && <button className="secondary-button" type="button" onClick={() => setDialogTask(null)}>Crear primera tarea</button>}</section>}
    {!!data?.items.length && <ul className="task-list" aria-label="Tareas del espacio">{data.items.map((task) => { const unresolved = task.status === "scheduled" || task.status === "pending"; const busy = resolution.isPending && resolution.variables?.task.id === task.id; return <li className="task-card" key={task.id}>
      <div className="task-card__main"><div className="task-card__heading"><h2>{task.title}</h2><span className={`task-status task-status--${task.status}`}>{statusLabels[task.status]}</span>{task.task_series_id && <span className="task-recurring">Recurrente</span>}</div>{task.description && <p>{task.description}</p>}<dl className="task-metadata"><div><dt>Programación</dt><dd>{formatTaskDate(task.scheduled_at, workspace.timezone)}</dd></div><div><dt>Categoría</dt><dd>{task.category_id ? categoryNames.get(task.category_id) ?? "Categoría no disponible" : "Sin categoría"}</dd></div><div><dt>Proyecto</dt><dd>{task.project_id ? projectNames.get(task.project_id) ?? "Proyecto no disponible" : "Sin proyecto"}</dd></div></dl></div>
      <div className="task-actions">{unresolved ? <><button className="secondary-button" type="button" onClick={() => setDialogTask(task)}>Editar <span className="sr-only">{task.title}</span></button>{(["completed", "not_completed", "cancelled"] as TaskOutcome[]).map((action) => <button key={action} className="secondary-button" type="button" disabled={busy} aria-label={`${statusLabels[action]}: ${task.title}`} onClick={() => resolution.mutate({ task, action })}>{action === "completed" ? "Completar" : action === "not_completed" ? "No realizar" : "Cancelar"}</button>)}</> : <span className="task-immutable">Tarea resuelta; no admite cambios.</span>}</div>
    </li>; })}</ul>}
    {data && data.total_pages > 0 && <nav className="task-pagination" aria-label="Paginación de tareas"><span>Página {data.page} de {data.total_pages} · {data.total} resultados</span><div><button className="secondary-button" type="button" disabled={data.page <= 1} onClick={() => setFilter("page", String(data.page - 1))}>Anterior</button><button className="secondary-button" type="button" disabled={data.page >= data.total_pages} onClick={() => setFilter("page", String(data.page + 1))}>Siguiente</button><select aria-label="Resultados por página" value={filters.pageSize} onChange={(e) => setFilter("page_size", e.target.value)}><option value="10">10</option><option value="20">20</option><option value="50">50</option><option value="100">100</option></select></div></nav>}
    {dialogTask !== undefined && <TaskDialog task={dialogTask} timezone={workspace.timezone} categories={categories} projects={projects} optionsLoading={categoriesQuery.isPending || projectsQuery.isPending} pending={saveMutation.isPending} error={formError} onClose={() => setDialogTask(undefined)} onSave={async (values) => { setFormError(null); await saveMutation.mutateAsync(values).catch(() => undefined); }} />}
  </div>;
}
