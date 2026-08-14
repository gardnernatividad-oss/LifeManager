import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { createPlanningProject, createPlanningProjectStep, getPlanningProject, listPlanningProjects, updatePlanningProject, updatePlanningProjectStep } from "../../api/planningProjectApi";
import { listAllCategoryOptions } from "../../api/planningPendingItemApi";
import { queryKeys } from "../../api/queryKeys";
import type { PlanningProject, PlanningProjectListParams, PlanningProjectStep, PlanningStepInput } from "../../types/planningProject";
import { formatShortCalendarDate } from "../../utils/localizedDate";
import { totalWeightHundredths, weightToHundredths } from "../../utils/projectWeight";

interface DraftStep { name: string; planned_date: string; weight: string; position: number }
const blankStep = (position = 0): DraftStep => ({ name: "", planned_date: "", weight: "", position });
const conflictMessage = "El Proyecto cambió desde la última carga. Actualizamos los datos; vuelve a intentarlo.";

function validateSteps(steps: DraftStep[], active: boolean): string | null {
  if (!active) return null;
  if (steps.length === 0) return "Un Proyecto activo requiere al menos un Paso.";
  if (steps.some((step) => !step.name.trim() || !step.planned_date || weightToHundredths(step.weight) === null)) return "Completa nombre, fecha y peso válido de todos los Pasos.";
  if (new Set(steps.map((step) => step.position)).size !== steps.length) return "Las posiciones de los Pasos no pueden repetirse.";
  if (totalWeightHundredths(steps) !== 10_000) return "El peso total debe ser exactamente 100.00.";
  return null;
}

function StepFields({ step, prefix, onChange }: { step: DraftStep; prefix: string; onChange: (step: DraftStep) => void }) {
  return <div className="project-planning-step-fields">
    <label>Posición<input aria-label={`Posición ${prefix}`} min="0" type="number" value={step.position} onChange={(event) => onChange({ ...step, position: Number(event.target.value) })} /></label>
    <label>Nombre<input aria-label={`Nombre ${prefix}`} value={step.name} onChange={(event) => onChange({ ...step, name: event.target.value })} /></label>
    <label>Fecha planificada<input aria-label={`Fecha ${prefix}`} type="date" value={step.planned_date} onChange={(event) => onChange({ ...step, planned_date: event.target.value })} /></label>
    <label>Peso<input aria-label={`Peso ${prefix}`} inputMode="decimal" placeholder="25.00" value={step.weight} onChange={(event) => onChange({ ...step, weight: event.target.value })} /></label>
  </div>;
}

export function PlanningProjectsPage() {
  const client = useQueryClient();
  const [params, setParams] = useState<PlanningProjectListParams>({ page: 1, page_size: 25 });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [name, setName] = useState(""); const [categoryId, setCategoryId] = useState(""); const [active, setActive] = useState(false);
  const [draftSteps, setDraftSteps] = useState<DraftStep[]>([]);
  const [projectEdit, setProjectEdit] = useState<{ name: string; categoryId: string; active: boolean; lockVersion: number } | null>(null);
  const [stepEdit, setStepEdit] = useState<(DraftStep & { id: string; lockVersion: number }) | null>(null);
  const [newStep, setNewStep] = useState<DraftStep>(blankStep());
  const [feedback, setFeedback] = useState<{ kind: "error" | "success"; text: string } | null>(null);
  const categories = useQuery({ queryKey: queryKeys.categoryOptions, queryFn: listAllCategoryOptions });
  const projects = useQuery({ queryKey: queryKeys.planningProjects(params), queryFn: () => listPlanningProjects(params) });
  const detail = useQuery({ queryKey: queryKeys.planningProjectDetail(selectedId ?? ""), queryFn: () => getPlanningProject(selectedId!), enabled: Boolean(selectedId) });

  async function refreshProject(id?: string) {
    await Promise.all([client.invalidateQueries({ queryKey: queryKeys.planningProjectsRoot }), ...(id ? [client.invalidateQueries({ queryKey: queryKeys.planningProjectDetail(id) })] : []), client.invalidateQueries({ queryKey: queryKeys.home }), client.invalidateQueries({ queryKey: queryKeys.review }), client.invalidateQueries({ queryKey: queryKeys.projectReportsRoot })]);
  }
  function mutationError(error: unknown, id?: string) {
    const conflict = axios.isAxiosError(error) && error.response?.status === 409;
    setProjectEdit(null); setStepEdit(null);
    setFeedback({ kind: "error", text: conflict ? conflictMessage : "No pudimos guardar los cambios del Proyecto." });
    if (id) void refreshProject(id);
  }

  const createProject = useMutation({ mutationFn: (payload: Parameters<typeof createPlanningProject>[0]) => createPlanningProject(payload), onSuccess: async (created) => { setName(""); setCategoryId(""); setActive(false); setDraftSteps([]); setSelectedId(created.id); setFeedback({ kind: "success", text: "Proyecto creado." }); await refreshProject(created.id); }, onError: (error) => mutationError(error) });
  const saveProject = useMutation({ mutationFn: ({ project, payload }: { project: PlanningProject; payload: { category_id: string; name: string; is_active: boolean; lock_version: number } }) => updatePlanningProject(project.id, payload), onSuccess: async (saved) => { setProjectEdit(null); setFeedback({ kind: "success", text: "Proyecto actualizado." }); await refreshProject(saved.id); }, onError: (error) => mutationError(error, selectedId ?? undefined) });
  const addStep = useMutation({ mutationFn: ({ projectId, step }: { projectId: string; step: PlanningStepInput }) => createPlanningProjectStep(projectId, step), onSuccess: async () => { setNewStep(blankStep((detail.data?.steps.length ?? 0) + 1)); setFeedback({ kind: "success", text: "Paso agregado." }); await refreshProject(selectedId!); }, onError: (error) => mutationError(error, selectedId ?? undefined) });
  const saveStep = useMutation({ mutationFn: ({ projectId, stepId, payload }: { projectId: string; stepId: string; payload: PlanningStepInput & { lock_version: number } }) => updatePlanningProjectStep(projectId, stepId, payload), onSuccess: async () => { setStepEdit(null); setFeedback({ kind: "success", text: "Paso actualizado." }); await refreshProject(selectedId!); }, onError: (error) => mutationError(error, selectedId ?? undefined) });

  function submitCreate(event: FormEvent) {
    event.preventDefault();
    if (!categoryId || !name.trim()) return setFeedback({ kind: "error", text: "Completa la Categoría y el nombre." });
    const issue = validateSteps(draftSteps, active); if (issue) return setFeedback({ kind: "error", text: issue });
    createProject.mutate({ category_id: categoryId, name: name.trim(), is_active: active, steps: draftSteps.map((step) => ({ ...step, name: step.name.trim(), planned_date: step.planned_date || null, weight: step.weight || null })) });
  }
  function beginProjectEdit(project: PlanningProject) { setProjectEdit({ name: project.name, categoryId: project.category_id, active: project.is_active, lockVersion: project.lock_version }); setFeedback(null); }
  function submitProjectEdit(event: FormEvent) {
    event.preventDefault(); if (!projectEdit || !detail.data) return;
    if (projectEdit.active && !detail.data.is_active) { const steps = detail.data.steps.map((step) => ({ name: step.name, planned_date: step.planned_date ?? "", weight: step.weight ?? "", position: step.position })); const issue = validateSteps(steps, true); if (issue) return setFeedback({ kind: "error", text: issue }); }
    saveProject.mutate({ project: detail.data, payload: { category_id: projectEdit.categoryId, name: projectEdit.name.trim(), is_active: projectEdit.active, lock_version: projectEdit.lockVersion } });
  }
  function beginStepEdit(step: PlanningProjectStep) { setStepEdit({ id: step.id, lockVersion: step.lock_version, name: step.name, planned_date: step.planned_date ?? "", weight: step.weight ?? "", position: step.position }); setFeedback(null); }
  function submitNewStep(event: FormEvent) { event.preventDefault(); if (!selectedId) return; if (!newStep.name.trim() || (newStep.weight && weightToHundredths(newStep.weight) === null)) return setFeedback({ kind: "error", text: "Completa un nombre y usa un peso válido." }); addStep.mutate({ projectId: selectedId, step: { ...newStep, name: newStep.name.trim(), planned_date: newStep.planned_date || null, weight: newStep.weight || null } }); }
  function submitStepEdit(event: FormEvent) { event.preventDefault(); if (!selectedId || !stepEdit) return; if (!stepEdit.name.trim() || (stepEdit.weight && weightToHundredths(stepEdit.weight) === null)) return setFeedback({ kind: "error", text: "Completa un nombre y usa un peso válido." }); saveStep.mutate({ projectId: selectedId, stepId: stepEdit.id, payload: { name: stepEdit.name.trim(), planned_date: stepEdit.planned_date || null, weight: stepEdit.weight || null, position: stepEdit.position, lock_version: stepEdit.lockVersion } }); }
  const categoryList = categories.data ?? [];

  return <section className="project-planning-page"><header><p className="eyebrow">Planificación</p><h1>Planificación · Proyectos</h1></header>
    <section className="project-planning-panel" aria-labelledby="project-create-title"><h2 id="project-create-title">Crear Proyecto</h2>
      {categories.isPending ? <p role="status">Cargando Categorías…</p> : categories.isError ? <div role="alert"><p>No pudimos cargar las Categorías.</p><button type="button" onClick={() => void categories.refetch()}>Reintentar</button></div> : categoryList.length === 0 ? <p>Aún no hay Categorías configuradas en Tablas &gt; Categorías.</p> : <form className="project-planning-create" onSubmit={submitCreate} noValidate>
        <label>Categoría<select required value={categoryId} onChange={(event) => setCategoryId(event.target.value)}><option value="">Selecciona una Categoría</option>{categoryList.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
        <label>Nombre<input required value={name} onChange={(event) => setName(event.target.value)} /></label><label>Vigencia<select value={active ? "active" : "inactive"} onChange={(event) => { const next = event.target.value === "active"; setActive(next); if (next && draftSteps.length === 0) setDraftSteps([blankStep(0)]); }}><option value="inactive">Inactivo</option><option value="active">Activo</option></select></label>
        <div className="project-planning-drafts"><div><strong>Pasos iniciales</strong><button type="button" onClick={() => setDraftSteps([...draftSteps, blankStep(draftSteps.length)])}>Agregar Paso</button></div>{draftSteps.map((step, index) => <StepFields key={index} prefix={`del Paso ${index + 1}`} step={step} onChange={(next) => setDraftSteps(draftSteps.map((row, rowIndex) => rowIndex === index ? next : row))} />)}<strong>Peso total: {draftSteps.length ? ((totalWeightHundredths(draftSteps) ?? 0) / 100).toFixed(2) : "0.00"}</strong></div>
        <button className="primary-button" disabled={createProject.isPending} type="submit">Crear</button>
      </form>}
    </section>
    <section className="project-planning-panel" aria-labelledby="project-register-title"><h2 id="project-register-title">Registro de Proyectos</h2>
      <div className="pending-planning-filters"><label>Vigencia<select value={params.is_active === undefined ? "" : String(params.is_active)} onChange={(event) => setParams({ ...params, page: 1, is_active: event.target.value === "" ? undefined : event.target.value === "true" })}><option value="">Todas</option><option value="true">Activos</option><option value="false">Inactivos</option></select></label><label>Categoría<select value={params.category_id ?? ""} onChange={(event) => setParams({ ...params, page: 1, category_id: event.target.value || undefined })}><option value="">Todas</option>{categoryList.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><label>Desde<input type="date" value={params.planned_from ?? ""} onChange={(event) => setParams({ ...params, page: 1, planned_from: event.target.value || undefined })} /></label><label>Hasta<input type="date" value={params.planned_to ?? ""} onChange={(event) => setParams({ ...params, page: 1, planned_to: event.target.value || undefined })} /></label></div>
      {feedback ? <p className={feedback.kind === "error" ? "review-notice review-notice--error" : "review-notice review-notice--success"} role={feedback.kind === "error" ? "alert" : "status"}>{feedback.text}</p> : null}
      {projects.isPending ? <p role="status">Cargando Proyectos…</p> : projects.isError ? <div role="alert"><p>No pudimos cargar los Proyectos.</p><button type="button" onClick={() => void projects.refetch()}>Reintentar</button></div> : projects.data.items.length === 0 ? <p className="review-empty">No hay Proyectos para los filtros seleccionados.</p> : <div role="table" aria-label="Registro de Proyectos" className="project-planning-table"><div role="row" className="project-planning-row project-planning-row--head"><span role="columnheader">Vigencia</span><span role="columnheader">Proyecto</span><span role="columnheader">Categoría</span><span role="columnheader">Fecha planificada</span><span role="columnheader">Acciones</span></div>{projects.data.items.map((project) => <div role="row" className="project-planning-row" key={project.id}><span role="cell">{project.is_active ? "Activo" : "Inactivo"}</span><strong role="cell">{project.name}</strong><span role="cell">{project.category.name}</span><span role="cell">{project.planned_date ? formatShortCalendarDate(project.planned_date) : "—"}</span><span role="cell"><button className="project-planning-open" type="button" aria-label={`Ver estructura de ${project.name}`} onClick={() => { setSelectedId(project.id); setProjectEdit(null); setStepEdit(null); }}>›</button></span></div>)}</div>}
      {projects.data ? <div className="planning-pagination"><span>Página {projects.data.page} de {Math.max(1, projects.data.total_pages)}</span><label>Por página<select value={params.page_size} onChange={(event) => setParams({ ...params, page: 1, page_size: Number(event.target.value) })}>{[25, 50, 100].map((size) => <option key={size}>{size}</option>)}</select></label><button type="button" disabled={params.page <= 1} onClick={() => setParams({ ...params, page: params.page - 1 })}>Anterior</button><button type="button" disabled={params.page >= projects.data.total_pages} onClick={() => setParams({ ...params, page: params.page + 1 })}>Siguiente</button></div> : null}
    </section>
    {selectedId ? <section className="project-planning-panel" aria-labelledby="project-detail-title"><h2 id="project-detail-title">Estructura del Proyecto</h2>{detail.isPending ? <p role="status">Cargando estructura…</p> : detail.isError ? <div role="alert"><p>No pudimos cargar la estructura.</p><button type="button" onClick={() => void detail.refetch()}>Reintentar</button></div> : detail.data ? <>
      {projectEdit ? <form className="project-planning-edit" onSubmit={submitProjectEdit}><label>Nombre del Proyecto<input value={projectEdit.name} onChange={(event) => setProjectEdit({ ...projectEdit, name: event.target.value })} /></label><label>Categoría del Proyecto<select value={projectEdit.categoryId} onChange={(event) => setProjectEdit({ ...projectEdit, categoryId: event.target.value })}>{categoryList.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><label>Vigencia del Proyecto<select value={projectEdit.active ? "active" : "inactive"} onChange={(event) => setProjectEdit({ ...projectEdit, active: event.target.value === "active" })}><option value="active">Activo</option><option value="inactive">Inactivo</option></select></label><button type="submit">Guardar Proyecto</button><button type="button" onClick={() => setProjectEdit(null)}>Cancelar</button></form> : <div className="project-planning-detail-heading"><div><strong>{detail.data.name}</strong><span>{detail.data.is_active ? "Activo" : "Inactivo"} · {detail.data.category.name}</span></div><button type="button" onClick={() => beginProjectEdit(detail.data)}>Editar Proyecto</button></div>}
      <p><strong>Peso total: {Number(detail.data.total_weight).toFixed(2)}</strong></p><div role="table" aria-label="Pasos del Proyecto" className="project-planning-table"><div role="row" className="project-planning-step-row project-planning-row--head"><span role="columnheader">Posición</span><span role="columnheader">Paso</span><span role="columnheader">Fecha</span><span role="columnheader">Peso</span><span role="columnheader">Acciones</span></div>{[...detail.data.steps].sort((a, b) => a.position - b.position || a.id.localeCompare(b.id)).map((step) => <div role="row" className="project-planning-step-row" key={step.id}>{stepEdit?.id === step.id ? <form className="project-planning-step-edit" onSubmit={submitStepEdit}><StepFields prefix={`de ${step.name}`} step={stepEdit} onChange={(next) => setStepEdit({ ...stepEdit, ...next })} /><span><button type="submit">Guardar Paso</button><button type="button" onClick={() => setStepEdit(null)}>Cancelar</button></span></form> : <><span role="cell">{step.position}</span><strong role="cell">{step.name}</strong><span role="cell">{step.planned_date ? formatShortCalendarDate(step.planned_date) : "—"}</span><span role="cell">{step.weight ?? "—"}</span><span role="cell"><button type="button" disabled={detail.data.is_active} aria-label={`Editar Paso ${step.name}`} onClick={() => beginStepEdit(step)}>Editar</button></span></>}</div>)}</div>
      {detail.data.is_active ? <p>Desactiva el Proyecto para modificar su estructura.</p> : <form className="project-planning-new-step" onSubmit={submitNewStep}><h3>Agregar Paso</h3><StepFields prefix="del nuevo Paso" step={newStep} onChange={setNewStep} /><button type="submit">Agregar Paso</button></form>}
    </> : null}</section> : null}
  </section>;
}
