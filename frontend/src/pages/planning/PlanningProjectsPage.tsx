import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { queryKeys } from "../../api/queryKeys";
import { createV2Project, deactivateV2Project, getV2Project, listV2Projects, reactivateV2Project, updateV2Project } from "../../api/v2ProjectApi";
import { listWorkspaceMembers, type WorkspaceMemberSummary } from "../../api/workspaceApi";
import { CategorySelector } from "../../components/common/V2CatalogSelector";
import { useAuth } from "../../hooks/useAuth";
import type { WorkspaceSummary } from "../../types/auth";
import type { V2Project, V2ProjectFilters, V2ProjectUpdate } from "../../types/v2Project";

const safeError = (error: unknown) => axios.isAxiosError(error) && error.response?.status === 409
  ? "El Proyecto cambió desde la última carga. Actualizamos los datos; vuelve a intentarlo."
  : "No pudimos guardar el Proyecto.";

export function PlanningProjectsPage() {
  const { workspace, user } = useAuth();
  if (!workspace || !user) return <section><h1>Planificación · Proyectos</h1><p>Selecciona un espacio.</p></section>;
  return <WorkspaceProjects key={workspace.id} workspace={workspace} />;
}

function WorkspaceProjects({ workspace }: { workspace: WorkspaceSummary }) {
  const client = useQueryClient();
  const workspaceId = workspace.id;
  const shared = workspace.kind === "SHARED";
  const [filters, setFilters] = useState<V2ProjectFilters>({ page: 1, page_size: 25 });
  const [categoryId, setCategoryId] = useState("");
  const [leaderId, setLeaderId] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editing, setEditing] = useState<V2Project | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const projects = useQuery({ queryKey: queryKeys.v2Projects(workspaceId, filters), queryFn: () => listV2Projects(workspaceId, filters) });
  const detail = useQuery({ queryKey: queryKeys.v2ProjectDetail(workspaceId, selectedId ?? ""), queryFn: () => getV2Project(workspaceId, selectedId!), enabled: Boolean(selectedId) });
  const members = useQuery({ queryKey: queryKeys.workspaceMembers(workspaceId), queryFn: () => listWorkspaceMembers(workspaceId), enabled: shared });
  const activeMembers = (members.data ?? []).filter((member) => member.status === "ACTIVE");
  const refresh = async (id?: string) => { await client.invalidateQueries({ queryKey: queryKeys.v2ProjectsRoot(workspaceId) }); if (id) await client.invalidateQueries({ queryKey: queryKeys.v2ProjectDetail(workspaceId, id) }); };
  const mutation = useMutation({ mutationFn: (operation: () => Promise<V2Project>) => operation(), onSuccess: async (saved) => { setEditing(null); setFeedback("Cambios guardados."); await refresh(saved.id); }, onError: async (error) => { setEditing(null); setFeedback(safeError(error)); await refresh(selectedId ?? undefined); } });

  function submitCreate(event: FormEvent) {
    event.preventDefault();
    if (!categoryId || !name.trim() || (shared && !leaderId)) { setFeedback("Completa los campos requeridos."); return; }
    mutation.mutate(() => createV2Project(workspaceId, { category_id: categoryId, ...(shared ? { leader_user_id: leaderId } : {}), name: name.trim(), description: description.trim() || null }).then((created) => { setName(""); setDescription(""); setSelectedId(created.id); return created; }));
  }

  return <section className="v2-project-page"><header><p className="eyebrow">Planificación</p><h1>Planificación · Proyectos</h1></header>
    <section className="project-planning-panel"><h2>Crear Proyecto</h2><form className="v2-project-form" onSubmit={submitCreate}><CategorySelector workspaceId={workspaceId} value={categoryId} onChange={setCategoryId} required /><label>Nombre<input required maxLength={255} value={name} onChange={(event) => setName(event.target.value)} /></label>{shared ? <LeaderSelector value={leaderId} members={activeMembers} onChange={setLeaderId} required /> : <p>Líder: tú</p>}<label>Descripción<textarea value={description} onChange={(event) => setDescription(event.target.value)} /></label><button className="primary-button" disabled={mutation.isPending}>Crear</button></form></section>
    <section className="project-planning-panel"><h2>Registro de Proyectos</h2><div className="v2-project-filters"><label>Vigencia<select value={filters.is_active === undefined ? "" : String(filters.is_active)} onChange={(event) => setFilters({ ...filters, page: 1, is_active: event.target.value === "" ? undefined : event.target.value === "true" })}><option value="">Todos</option><option value="true">Activos</option><option value="false">Inactivos</option></select></label><CategorySelector workspaceId={workspaceId} value={filters.category_id ?? ""} onChange={(value) => setFilters({ ...filters, page: 1, category_id: value || undefined })} />{shared ? <LeaderSelector value={filters.leader_user_id ?? ""} members={activeMembers} onChange={(value) => setFilters({ ...filters, page: 1, leader_user_id: value || undefined })} /> : null}<label>Buscar<input type="search" maxLength={255} value={filters.search ?? ""} onChange={(event) => setFilters({ ...filters, page: 1, search: event.target.value || undefined })} /></label></div>
      {feedback ? <p role="status">{feedback}</p> : null}{projects.isPending ? <p role="status">Cargando Proyectos…</p> : projects.isError ? <div role="alert"><p>No pudimos cargar los Proyectos.</p><button type="button" onClick={() => void projects.refetch()}>Reintentar</button></div> : projects.data.items.length === 0 ? <p className="review-empty">No existen Proyectos.</p> : <div className="v2-project-list">{projects.data.items.map((project) => <ProjectRow key={project.id} project={project} pending={mutation.isPending} onView={() => setSelectedId(project.id)} onEdit={() => setEditing(project)} onLifecycle={() => mutation.mutate(() => project.is_active ? deactivateV2Project(workspaceId, project.id, project.lock_version) : reactivateV2Project(workspaceId, project.id, project.lock_version))} />)}</div>}
      {projects.data ? <div className="planning-pagination"><span>Página {projects.data.page} de {Math.max(1, projects.data.total_pages)}</span><label>Por página<select value={filters.page_size} onChange={(event) => setFilters({ ...filters, page: 1, page_size: Number(event.target.value) })}><option>25</option><option>50</option><option>100</option></select></label><button type="button" disabled={filters.page <= 1} onClick={() => setFilters({ ...filters, page: filters.page - 1 })}>Anterior</button><button type="button" disabled={filters.page >= projects.data.total_pages} onClick={() => setFilters({ ...filters, page: filters.page + 1 })}>Siguiente</button></div> : null}</section>
    {detail.data ? <section className="project-planning-panel"><h2>{detail.data.name}</h2><p>{detail.data.description || "Sin descripción"}</p><p>{detail.data.category_name} · Líder: {detail.data.leader_display_name}</p><p>Avance, Estado y Cumplimiento: disponibles con Etapas en 7.2.</p><button type="button" onClick={() => setSelectedId(null)}>Cerrar</button></section> : null}
    {editing ? <ProjectEditDialog project={editing} workspaceId={workspaceId} shared={shared} members={activeMembers} pending={mutation.isPending} onClose={() => setEditing(null)} onSave={(payload) => mutation.mutate(() => updateV2Project(workspaceId, editing.id, payload))} /> : null}
  </section>;
}

function LeaderSelector({ value, members, onChange, required = false }: { value: string; members: WorkspaceMemberSummary[]; onChange: (value: string) => void; required?: boolean }) { return <label>Líder<select required={required} value={value} onChange={(event) => onChange(event.target.value)}><option value="">{required ? "Selecciona una persona" : "Todos"}</option>{members.map((member) => <option key={member.user_id} value={member.user_id}>{member.display_name}</option>)}</select></label>; }
function ProjectRow({ project, pending, onView, onEdit, onLifecycle }: { project: V2Project; pending: boolean; onView: () => void; onEdit: () => void; onLifecycle: () => void }) { return <article className="v2-project-row"><div><strong>{project.name}</strong><small>{project.category_name} · {project.leader_display_name}</small></div><span>{project.is_active ? "Activo" : "Inactivo"}</span><span>Avance: —</span><div><button type="button" onClick={onView}>Ver</button>{project.can_edit ? <button type="button" onClick={onEdit}>Editar</button> : null}<button type="button" disabled={pending} onClick={onLifecycle}>{project.is_active ? "Desactivar" : "Reactivar"}</button></div></article>; }
function ProjectEditDialog({ project, workspaceId, shared, members, pending, onClose, onSave }: { project: V2Project; workspaceId: string; shared: boolean; members: WorkspaceMemberSummary[]; pending: boolean; onClose: () => void; onSave: (payload: V2ProjectUpdate) => void }) { const [categoryId, setCategoryId] = useState(project.category_id); const [leaderId, setLeaderId] = useState(project.leader_user_id); return <dialog open><form onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); onSave({ category_id: categoryId, ...(shared ? { leader_user_id: leaderId } : {}), name: String(data.get("name")).trim(), description: String(data.get("description")).trim() || null, lock_version: project.lock_version }); }}><h2>Editar {project.name}</h2><CategorySelector workspaceId={workspaceId} currentId={project.category_id} value={categoryId} onChange={setCategoryId} required /><label>Nombre<input name="name" required maxLength={255} defaultValue={project.name} /></label>{shared ? <LeaderSelector value={leaderId} members={members} onChange={setLeaderId} required /> : null}<label>Descripción<textarea name="description" defaultValue={project.description ?? ""} /></label><button disabled={pending}>Guardar</button><button type="button" onClick={onClose}>Cancelar</button></form></dialog>; }
