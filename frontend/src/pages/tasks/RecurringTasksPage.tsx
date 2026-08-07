import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { listCategories } from "../../api/categoryApi";
import { listProjects } from "../../api/projectApi";
import { queryKeys } from "../../api/queryKeys";
import { activateTaskSeries, createTaskSeries, deactivateTaskSeries, listTaskSeries, materializeTaskSeries, synchronizeTaskSeries, updateTaskSeries } from "../../api/taskSeriesApi";
import { useAuth } from "../../hooks/useAuth";
import { useWorkspaces } from "../../hooks/useWorkspaces";
import type { MaterializationResponse, SynchronizationResponse, TaskSeries, TaskSeriesWindow, TaskSeriesWrite } from "../../types/taskSeries";
import { formatTaskDate, isoToLocalInput, localDateTimeToIso } from "../../utils/taskDateTime";

type ActiveFilter = "all" | "active" | "inactive";
const weekdays = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];
const seriesSchema = z.object({
  title: z.string().trim().min(1, "Ingresa un título.").max(255, "El título no puede superar 255 caracteres."),
  description: z.string(), timezone: z.string().trim().min(1, "Ingresa una zona horaria IANA."),
  frequency: z.enum(["daily", "weekly", "monthly"]), interval: z.number().int().min(1).max(365),
  weekdays: z.array(z.string()), monthDay: z.number().int().min(1).max(31).optional(),
  startsAt: z.string().min(1, "Selecciona el inicio."), endsAt: z.string(), categoryId: z.string(), projectId: z.string()
}).superRefine((value, context) => {
  if (value.frequency === "weekly" && value.weekdays.length === 0) context.addIssue({ code: "custom", path: ["weekdays"], message: "Selecciona al menos un día." });
  if (value.frequency === "monthly" && !value.monthDay) context.addIssue({ code: "custom", path: ["monthDay"], message: "Selecciona el día del mes." });
  if (value.endsAt && value.startsAt && value.endsAt <= value.startsAt) context.addIssue({ code: "custom", path: ["endsAt"], message: "El fin debe ser posterior al inicio." });
});
type SeriesForm = z.infer<typeof seriesSchema>;

function summary(series: TaskSeries) {
  const time = new Intl.DateTimeFormat("es-PE", { timeZone: series.timezone, hour: "2-digit", minute: "2-digit" }).format(new Date(series.starts_at));
  if (series.frequency === "daily") return series.interval === 1 ? `Todos los días a las ${time}` : `Cada ${series.interval} días a las ${time}`;
  if (series.frequency === "weekly") {
    const prefix = series.interval === 1 ? "Cada semana" : `Cada ${series.interval} semanas`;
    return `${prefix}: ${(series.weekdays ?? []).map((day) => weekdays[day]).join(", ")} a las ${time}`;
  }
  return `${series.interval === 1 ? "Cada mes" : `Cada ${series.interval} meses`}, el día ${series.month_day}, a las ${time}`;
}

function friendlyError(error: unknown, operation: string) {
  if (error instanceof Error && error.message.startsWith("La hora seleccionada")) return error.message;
  if (axios.isAxiosError(error) && (error.response?.status === 409 || error.response?.status === 422)) return `No pudimos ${operation}. Revisa el rango, la recurrencia y sus asociaciones.`;
  return `No pudimos ${operation}. Intenta nuevamente.`;
}

function SeriesDialog({ series, workspaceTimezone, categories, projects, pending, error, onClose, onSave }: {
  series: TaskSeries | null; workspaceTimezone: string; categories: { id: string; name: string; is_active: boolean }[]; projects: { id: string; name: string; is_active: boolean }[];
  pending: boolean; error: string | null; onClose: () => void; onSave: (values: SeriesForm) => Promise<void>;
}) {
  const { register, control, handleSubmit, formState: { errors } } = useForm<SeriesForm>({ resolver: zodResolver(seriesSchema), defaultValues: {
    title: series?.title ?? "", description: series?.description ?? "", timezone: series?.timezone ?? workspaceTimezone,
    frequency: series?.frequency ?? "daily", interval: series?.interval ?? 1, weekdays: (series?.weekdays ?? []).map(String), monthDay: series?.month_day ?? undefined,
    startsAt: series ? isoToLocalInput(series.starts_at, series.timezone) : "", endsAt: series?.ends_at ? isoToLocalInput(series.ends_at, series.timezone) : "",
    categoryId: series?.category_id ?? "", projectId: series?.project_id ?? ""
  }});
  const frequency = useWatch({ control, name: "frequency" });
  return <div className="dialog-backdrop"><section className="series-dialog" role="dialog" aria-modal="true" aria-labelledby="series-dialog-title"><h2 id="series-dialog-title">{series ? "Editar recurrencia" : "Nueva recurrencia"}</h2><form onSubmit={handleSubmit(onSave)} noValidate>
    <div className="form-field"><label htmlFor="series-title">Título</label><input id="series-title" autoFocus {...register("title")} />{errors.title && <span className="field-error">{errors.title.message}</span>}</div>
    <div className="form-field"><label htmlFor="series-description">Descripción (opcional)</label><textarea id="series-description" rows={3} {...register("description")} /></div>
    <div className="series-form-grid"><div className="form-field"><label htmlFor="series-timezone">Zona horaria IANA</label><input id="series-timezone" {...register("timezone")} /></div><div className="form-field"><label htmlFor="series-frequency">Frecuencia</label><select id="series-frequency" {...register("frequency")}><option value="daily">Diaria</option><option value="weekly">Semanal</option><option value="monthly">Mensual</option></select></div><div className="form-field"><label htmlFor="series-interval">Intervalo</label><input id="series-interval" type="number" min="1" max="365" {...register("interval", { valueAsNumber: true })} /></div></div>
    {frequency === "weekly" && <fieldset className="weekday-field"><legend>Días de la semana</legend>{weekdays.map((day, index) => <label key={day}><input type="checkbox" value={index} {...register("weekdays")} />{day}</label>)}{errors.weekdays && <span className="field-error">{errors.weekdays.message}</span>}</fieldset>}
    {frequency === "monthly" && <div className="form-field"><label htmlFor="series-month-day">Día del mes</label><input id="series-month-day" type="number" min="1" max="31" {...register("monthDay", { valueAsNumber: true })} />{errors.monthDay && <span className="field-error">{errors.monthDay.message}</span>}</div>}
    <div className="series-form-grid"><div className="form-field"><label htmlFor="series-start">Inicio local</label><input id="series-start" type="datetime-local" {...register("startsAt")} />{errors.startsAt && <span className="field-error">{errors.startsAt.message}</span>}</div><div className="form-field"><label htmlFor="series-end">Fin local (opcional)</label><input id="series-end" type="datetime-local" {...register("endsAt")} />{errors.endsAt && <span className="field-error">{errors.endsAt.message}</span>}</div></div>
    <div className="series-form-grid"><div className="form-field"><label htmlFor="series-category">Categoría</label><select id="series-category" {...register("categoryId")}><option value="">Sin categoría</option>{categories.map((item) => <option key={item.id} value={item.id} disabled={!item.is_active && item.id !== series?.category_id}>{item.name}{!item.is_active ? " (inactiva)" : ""}</option>)}</select></div><div className="form-field"><label htmlFor="series-project">Proyecto</label><select id="series-project" {...register("projectId")}><option value="">Sin proyecto</option>{projects.map((item) => <option key={item.id} value={item.id} disabled={!item.is_active && item.id !== series?.project_id}>{item.name}{!item.is_active ? " (inactivo)" : ""}</option>)}</select></div></div>
    {error && <div className="form-alert" role="alert">{error}</div>}<div className="dialog-actions"><button className="secondary-button" type="button" disabled={pending} onClick={onClose}>Cerrar</button><button className="primary-button" type="submit" disabled={pending}>{pending ? "Guardando…" : "Guardar recurrencia"}</button></div>
  </form></section></div>;
}

function WindowDialog({ series, mode, pending, error, onClose, onSubmit }: { series: TaskSeries; mode: "materialize" | "sync"; pending: boolean; error: string | null; onClose: () => void; onSubmit: (window: TaskSeriesWindow) => Promise<void> }) {
  const schema = z.object({ start: z.string().min(1, "Selecciona el inicio."), end: z.string().min(1, "Selecciona el fin.") }).refine((value) => value.end >= value.start, { path: ["end"], message: "El fin debe ser igual o posterior al inicio." });
  const { register, handleSubmit, formState: { errors } } = useForm<{ start: string; end: string }>({ resolver: zodResolver(schema), defaultValues: { start: "", end: "" } });
  const [conversionError, setConversionError] = useState<string | null>(null);
  return <div className="dialog-backdrop"><section className="series-dialog series-window-dialog" role="dialog" aria-modal="true" aria-labelledby="window-title"><h2 id="window-title">{mode === "materialize" ? "Materializar tareas" : "Sincronizar tareas futuras"}</h2>{mode === "sync" && <p>Actualiza las tareas futuras no resueltas de esta recurrencia para que coincidan con su configuración actual.</p>}<form onSubmit={handleSubmit(async (values) => { try { setConversionError(null); await onSubmit({ window_start: localDateTimeToIso(values.start, series.timezone), window_end: localDateTimeToIso(values.end, series.timezone) }); } catch (caught) { setConversionError(caught instanceof Error && caught.message.startsWith("La hora seleccionada") ? caught.message : "No pudimos interpretar el rango seleccionado."); } })}><div className="form-field"><label htmlFor="window-start">Inicio ({series.timezone})</label><input id="window-start" type="datetime-local" {...register("start")} />{errors.start && <span className="field-error">{errors.start.message}</span>}</div><div className="form-field"><label htmlFor="window-end">Fin ({series.timezone})</label><input id="window-end" type="datetime-local" {...register("end")} />{errors.end && <span className="field-error">{errors.end.message}</span>}</div>{(error || conversionError) && <div className="form-alert" role="alert">{error || conversionError}</div>}<div className="dialog-actions"><button className="secondary-button" type="button" disabled={pending} onClick={onClose}>Cerrar</button><button className="primary-button" type="submit" disabled={pending}>{pending ? "Procesando…" : mode === "materialize" ? "Materializar" : "Sincronizar"}</button></div></form></section></div>;
}

export function RecurringTasksPage() {
  const { workspace } = useAuth(); const workspaces = useWorkspaces(); const queryClient = useQueryClient(); const workspaceId = workspace?.id ?? "";
  const [filter, setFilter] = useState<ActiveFilter>("all"); const [editor, setEditor] = useState<TaskSeries | null | undefined>(); const [windowAction, setWindowAction] = useState<{ series: TaskSeries; mode: "materialize" | "sync" }>();
  const [formError, setFormError] = useState<string | null>(null); const [operationError, setOperationError] = useState<string | null>(null); const [notice, setNotice] = useState<string | null>(null);
  const active = filter === "all" ? null : filter === "active";
  const seriesQuery = useQuery({ queryKey: queryKeys.taskSeries(workspaceId, active), queryFn: () => listTaskSeries(workspaceId, active), enabled: !!workspaceId });
  const categoriesQuery = useQuery({ queryKey: queryKeys.categories(workspaceId, null), queryFn: () => listCategories(workspaceId, null), enabled: !!workspaceId });
  const projectsQuery = useQuery({ queryKey: queryKeys.projects(workspaceId, null), queryFn: () => listProjects(workspaceId, null), enabled: !!workspaceId });
  const invalidateSeries = () => queryClient.invalidateQueries({ queryKey: queryKeys.taskSeriesForWorkspace(workspaceId) });
  const invalidateGenerated = () => Promise.all([invalidateSeries(), queryClient.invalidateQueries({ queryKey: queryKeys.tasksForWorkspace(workspaceId) }), queryClient.invalidateQueries({ queryKey: queryKeys.dashboardSummary(workspaceId) }), queryClient.invalidateQueries({ queryKey: queryKeys.dashboardStatistics(workspaceId) })]);
  const save = useMutation({ mutationFn: (values: SeriesForm) => { const zone = values.timezone.trim(); const payload: TaskSeriesWrite = { title: values.title.trim(), description: values.description.trim() || null, timezone: zone, frequency: values.frequency, interval: values.interval, weekdays: values.frequency === "weekly" ? values.weekdays.map(Number) : null, month_day: values.frequency === "monthly" ? values.monthDay ?? null : null, starts_at: localDateTimeToIso(values.startsAt, zone), ends_at: values.endsAt ? localDateTimeToIso(values.endsAt, zone) : null, category_id: values.categoryId || null, project_id: values.projectId || null }; return editor ? updateTaskSeries(workspaceId, editor.id, payload) : createTaskSeries(workspaceId, payload); }, onSuccess: async () => { const editing = !!editor; await invalidateSeries(); setEditor(undefined); setFormError(null); setNotice(editing ? "La recurrencia fue actualizada. Usa Sincronizar para aplicar los cambios a tareas futuras generadas." : "Recurrencia creada."); }, onError: (error) => setFormError(friendlyError(error, "guardar la recurrencia")) });
  const lifecycle = useMutation({ mutationFn: (series: TaskSeries) => series.is_active ? deactivateTaskSeries(workspaceId, series.id) : activateTaskSeries(workspaceId, series.id), onSuccess: async (series) => { await invalidateSeries(); setNotice(series.is_active ? "Recurrencia activada." : "Recurrencia desactivada."); }, onError: (error) => setOperationError(friendlyError(error, "cambiar el estado")) });
  const windowMutation = useMutation<MaterializationResponse | SynchronizationResponse, unknown, { action: NonNullable<typeof windowAction>; window: TaskSeriesWindow }>({ mutationFn: async ({ action, window }) => action.mode === "materialize" ? materializeTaskSeries(workspaceId, action.series.id, window) : synchronizeTaskSeries(workspaceId, action.series.id, window), onSuccess: async (result) => { await invalidateGenerated(); if ("generated_count" in result) setNotice(result.generated_count ? `Se generaron ${result.generated_count} tareas.` : "No había nuevas tareas por generar en ese rango."); else setNotice(`Sincronización completada: ${result.created_count} creadas, ${result.updated_count} actualizadas y ${result.deleted_count} eliminadas.`); setWindowAction(undefined); setOperationError(null); }, onError: (error) => setOperationError(friendlyError(error, windowAction?.mode === "sync" ? "sincronizar" : "materializar")) });
  if (workspaces.isPending || (workspaces.data?.length && !workspace)) return <div className="series-list-skeleton" role="status" aria-label="Cargando tareas recurrentes" />;
  if (!workspace) return <section className="series-empty"><h1>No hay un espacio de trabajo disponible</h1><p>Selecciona un espacio para administrar recurrencias.</p></section>;
  const categories = categoriesQuery.data ?? []; const projects = projectsQuery.data ?? []; const categoryNames = new Map(categories.map((item) => [item.id, item.name])); const projectNames = new Map(projects.map((item) => [item.id, item.name]));
  return <div className="series-page"><header className="series-header"><div><p className="eyebrow">{workspace.name}</p><h1>Tareas recurrentes</h1><p>Define patrones y genera sus tareas de forma explícita.</p></div><button className="primary-button" onClick={() => { setFormError(null); setEditor(null); }}>Nueva recurrencia</button></header>
    <div className="series-filters" aria-label="Filtrar recurrencias">{(["all", "active", "inactive"] as ActiveFilter[]).map((value) => <button key={value} className={filter === value ? "filter-button filter-button--active" : "filter-button"} aria-pressed={filter === value} onClick={() => setFilter(value)}>{value === "all" ? "Todas" : value === "active" ? "Activas" : "Inactivas"}</button>)}</div>
    {notice && <div className="success-notice" role="status">{notice}</div>}{operationError && !windowAction && <div className="form-alert" role="alert">{operationError}</div>}
    {seriesQuery.isPending && <div className="series-list-skeleton" role="status" aria-label="Cargando tareas recurrentes" />}{seriesQuery.isError && <div className="dashboard-error" role="alert"><p>No pudimos cargar las tareas recurrentes.</p><button className="secondary-button" onClick={() => void seriesQuery.refetch()}>Reintentar</button></div>}
    {seriesQuery.data?.items.length === 0 && <section className="series-empty"><h2>{filter === "all" ? "Aún no tienes tareas recurrentes." : "No hay recurrencias con este estado."}</h2>{filter === "all" && <button className="secondary-button" onClick={() => setEditor(null)}>Crear primera recurrencia</button>}</section>}
    {!!seriesQuery.data?.items.length && <ul className="series-list" aria-label="Recurrencias del espacio">{seriesQuery.data.items.map((series) => <li className="series-card" key={series.id}><div><div className="series-card__heading"><h2>{series.title}</h2><span className="status-badge">{series.is_active ? "Activa" : "Inactiva"}</span></div>{series.description && <p>{series.description}</p>}<p className="series-summary">{summary(series)}</p><dl className="series-metadata"><div><dt>Zona horaria</dt><dd>{series.timezone}</dd></div><div><dt>Inicio</dt><dd>{formatTaskDate(series.starts_at, series.timezone)}</dd></div><div><dt>Fin</dt><dd>{series.ends_at ? formatTaskDate(series.ends_at, series.timezone) : "Sin fecha de fin"}</dd></div><div><dt>Categoría</dt><dd>{series.category_id ? categoryNames.get(series.category_id) ?? "Categoría no disponible" : "Sin categoría"}</dd></div><div><dt>Proyecto</dt><dd>{series.project_id ? projectNames.get(series.project_id) ?? "Proyecto no disponible" : "Sin proyecto"}</dd></div></dl></div><div className="series-actions"><button className="secondary-button" onClick={() => { setFormError(null); setEditor(series); }}>Editar {series.title}</button><button className="secondary-button" onClick={() => lifecycle.mutate(series)} disabled={lifecycle.isPending}>{series.is_active ? "Desactivar" : "Activar"} {series.title}</button><button className="secondary-button" onClick={() => { setOperationError(null); setWindowAction({ series, mode: "materialize" }); }} disabled={!series.is_active}>Materializar {series.title}</button><button className="secondary-button" onClick={() => { setOperationError(null); setWindowAction({ series, mode: "sync" }); }} disabled={!series.is_active}>Sincronizar {series.title}</button></div></li>)}</ul>}
    {editor !== undefined && <SeriesDialog series={editor} workspaceTimezone={workspace.timezone} categories={categories} projects={projects} pending={save.isPending} error={formError} onClose={() => setEditor(undefined)} onSave={async (values) => { await save.mutateAsync(values).catch(() => undefined); }} />}
    {windowAction && <WindowDialog series={windowAction.series} mode={windowAction.mode} pending={windowMutation.isPending} error={operationError} onClose={() => setWindowAction(undefined)} onSubmit={async (window) => { await windowMutation.mutateAsync({ action: windowAction, window }).catch(() => undefined); }} />}
  </div>;
}
