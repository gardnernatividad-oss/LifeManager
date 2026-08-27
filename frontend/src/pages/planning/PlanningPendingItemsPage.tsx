import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { CategorySelector } from "../../components/common/V2CatalogSelector";
import { queryKeys } from "../../api/queryKeys";
import { listWorkspaceMembers } from "../../api/workspaceApi";
import { correctV2PendingItem, createV2PendingItem, deactivateV2PendingItem, deleteV2PendingItem, listV2PendingItems, reactivateV2PendingItem, updateV2PendingItem, updateV2PendingItemProgress } from "../../api/v2PendingItemApi";
import { useAuth } from "../../hooks/useAuth";
import type { V2PendingItem } from "../../types/v2PendingItem";
import type { WorkspaceSummary } from "../../types/auth";
import { formatShortCalendarDate } from "../../utils/localizedDate";
import { Link } from "react-router-dom";

const safeError = (error: unknown) => axios.isAxiosError(error) && error.response?.status === 409
  ? "El Pendiente cambió desde la última carga. Actualizamos el registro; vuelve a intentarlo."
  : "No pudimos guardar el Pendiente.";

export function PlanningPendingItemsPage() {
  const { workspace, user } = useAuth();
  if (!workspace || !user) return <section><h1>Planificación · Pendientes</h1><p>Selecciona un espacio.</p></section>;
  return <WorkspacePendingItems key={workspace.id} workspace={workspace} userId={user.id} />;
}

function WorkspacePendingItems({ workspace, userId }: { workspace: WorkspaceSummary; userId: string }) {
  const client = useQueryClient();
  const workspaceId = workspace.id;
  const shared = workspace.kind === "SHARED";
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [categoryId, setCategoryId] = useState("");
  const [responsibleId, setResponsibleId] = useState("");
  const [name, setName] = useState("");
  const [plannedDate, setPlannedDate] = useState("");
  const [editing, setEditing] = useState<V2PendingItem | null>(null);
  const [progressing, setProgressing] = useState<V2PendingItem | null>(null);
  const [progress, setProgress] = useState(0);
  const [reactivating, setReactivating] = useState<V2PendingItem | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const items = useQuery({ queryKey: queryKeys.v2PendingItems(workspaceId, page, pageSize), queryFn: () => listV2PendingItems(workspaceId, page, pageSize), enabled: Boolean(workspaceId) });
  const members = useQuery({ queryKey: queryKeys.workspaceMembers(workspaceId), queryFn: () => listWorkspaceMembers(workspaceId), enabled: Boolean(workspaceId && shared) });
  const refresh = async () => client.invalidateQueries({ queryKey: queryKeys.v2PendingItemsRoot(workspaceId) });
  const mutation = useMutation({ mutationFn: (operation: () => Promise<unknown>) => operation(), onSuccess: async () => { setEditing(null); setProgressing(null); setReactivating(null); setFeedback("Cambios guardados."); await refresh(); }, onError: async (error) => { setEditing(null); setProgressing(null); setReactivating(null); setFeedback(safeError(error)); await refresh(); } });

  const responsible = shared ? responsibleId : userId;
  function submitCreate(event: FormEvent) {
    event.preventDefault(); setFeedback(null);
    if (!categoryId || !name.trim() || !plannedDate || !responsible) { setFeedback("Completa los campos requeridos."); return; }
    mutation.mutate(() => createV2PendingItem(workspaceId, { category_id: categoryId, responsible_user_id: shared ? responsible : undefined, name: name.trim(), planned_date: plannedDate }).then((value) => { setName(""); setPlannedDate(""); return value; }));
  }

  return <section className="pending-planning-page">
    <header><p className="eyebrow">Planificación</p><h1>Planificación · Pendientes</h1></header>
    <section className="pending-planning-panel"><h2>Crear Pendiente</h2><form className="pending-planning-form" onSubmit={submitCreate}>
      <CategorySelector workspaceId={workspaceId} value={categoryId} onChange={setCategoryId} required />
      <label>Nombre<input required maxLength={255} value={name} onChange={(event) => setName(event.target.value)} /></label>
      {shared ? <label>Responsable<select required value={responsibleId} onChange={(event) => setResponsibleId(event.target.value)}><option value="">Selecciona una persona</option>{(members.data ?? []).filter((member) => member.status === "ACTIVE").map((member) => <option key={member.user_id} value={member.user_id}>{member.display_name}</option>)}</select></label> : null}
      <label>Fecha planificada<input required type="date" value={plannedDate} onChange={(event) => setPlannedDate(event.target.value)} /></label>
      <button className="primary-button" disabled={mutation.isPending} type="submit">Crear</button>
    </form></section>
    <section className="pending-planning-panel"><h2>Registro de Pendientes</h2>
      {feedback ? <p className="review-notice" role="status">{feedback}</p> : null}
      {items.isPending ? <p role="status">Cargando Pendientes…</p> : items.isError ? <div role="alert"><p>No pudimos cargar los Pendientes.</p><button type="button" onClick={() => void items.refetch()}>Reintentar</button></div> : items.data.items.length === 0 ? <p className="review-empty">No hay Pendientes.</p> : <div className="v2-pending-list">{items.data.items.map((item) => <PendingRow key={item.id} item={item} mutationPending={mutation.isPending} onEdit={() => setEditing(item)} onProgress={() => { setProgressing(item); setProgress(item.progress); }} onDeactivate={() => mutation.mutate(() => deactivateV2PendingItem(workspaceId, item.id, item.lock_version))} onReactivate={() => setReactivating(item)} onDelete={() => { if (window.confirm(`¿Eliminar ${item.name}?`)) mutation.mutate(() => deleteV2PendingItem(workspaceId, item.id, item.lock_version)); }} />)}</div>}
      {items.data ? <div className="planning-pagination"><span>Página {items.data.page} de {Math.max(1, items.data.total_pages)}</span><label>Por página<select value={pageSize} onChange={(event) => { setPage(1); setPageSize(Number(event.target.value)); }}><option>25</option><option>50</option><option>100</option></select></label><button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)}>Anterior</button><button type="button" disabled={page >= items.data.total_pages} onClick={() => setPage(page + 1)}>Siguiente</button></div> : null}
    </section>
    {editing ? <dialog open><form onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); mutation.mutate(() => updateV2PendingItem(workspaceId, editing.id, { name: String(data.get("name")), category_id: editing.category_id, responsible_user_id: shared ? String(data.get("responsible")) : editing.responsible_user_id, planned_date: String(data.get("date")), lock_version: editing.lock_version })); }}><h2>Editar {editing.name}</h2><CategorySelector workspaceId={workspaceId} currentId={editing.category_id} value={editing.category_id} onChange={(value) => setEditing({ ...editing, category_id: value })} required /><label>Nombre<input name="name" defaultValue={editing.name} required /></label>{shared ? <label>Responsable<select name="responsible" defaultValue={editing.responsible_user_id}>{(members.data ?? []).filter((member) => member.status === "ACTIVE").map((member) => <option key={member.user_id} value={member.user_id}>{member.display_name}</option>)}</select></label> : null}<label>Fecha planificada<input name="date" type="date" defaultValue={editing.planned_date ?? ""} required /></label><button>Guardar</button><button type="button" onClick={() => setEditing(null)}>Cancelar</button></form></dialog> : null}
    {progressing ? <dialog open><form onSubmit={(event) => { event.preventDefault(); mutation.mutate(() => progressing.can_correct ? correctV2PendingItem(workspaceId, progressing.id, progress, progressing.lock_version) : updateV2PendingItemProgress(workspaceId, progressing.id, progress, progressing.lock_version)); }}><h2>{progressing.can_correct ? "Corregir" : "Actualizar avance"} {progressing.name}</h2>{progressing.can_correct ? <p>La corrección reabre el Pendiente y conserva el historial.</p> : null}<label>Avance<input type="number" min="0" max={progressing.can_correct ? 99 : 100} value={progress} onChange={(event) => setProgress(Number(event.target.value))} /></label><button>Guardar</button><button type="button" onClick={() => setProgressing(null)}>Cancelar</button></form></dialog> : null}
    {reactivating ? <dialog open><form onSubmit={(event) => { event.preventDefault(); const date = String(new FormData(event.currentTarget).get("date")); mutation.mutate(() => reactivateV2PendingItem(workspaceId, reactivating.id, date, reactivating.lock_version)); }}><h2>Reactivar {reactivating.name}</h2><label>Nueva fecha planificada<input name="date" type="date" required /></label><button>Reactivar</button><button type="button" onClick={() => setReactivating(null)}>Cancelar</button></form></dialog> : null}
  </section>;
}

function PendingRow({ item, mutationPending, onEdit, onProgress, onDeactivate, onReactivate, onDelete }: { item: V2PendingItem; mutationPending: boolean; onEdit: () => void; onProgress: () => void; onDeactivate: () => void; onReactivate: () => void; onDelete: () => void }) {
  const detail = item.compliance_detail_days === null ? "—" : `${item.compliance_detail_days} día(s)`;
  return <article className="v2-pending-row"><div><strong>{item.name}</strong><small>{item.category_name} · {item.responsible_display_name}</small></div><span>{item.planned_date ? formatShortCalendarDate(item.planned_date) : "—"}</span><span>{item.progress}% · {item.state}</span><span>{item.compliance ?? "—"} · {detail}</span><div className="pending-planning-actions"><Link aria-label={`Ver detalle de ${item.name}`} to={`/planificacion/pendientes/${item.id}`}>›</Link>{item.can_edit ? <button type="button" disabled={mutationPending} onClick={onEdit}>Editar</button> : null}{item.can_update_progress ? <button type="button" disabled={mutationPending} onClick={onProgress}>Avance</button> : null}{item.can_correct ? <button type="button" aria-label={`Corregir ${item.name}`} disabled={mutationPending} onClick={onProgress}>Corregir</button> : null}{item.can_deactivate ? <button type="button" disabled={mutationPending} onClick={onDeactivate}>Desactivar</button> : null}{item.can_reactivate ? <button type="button" disabled={mutationPending} onClick={onReactivate}>Reactivar</button> : null}{item.can_delete ? <button type="button" disabled={mutationPending} onClick={onDelete}>Eliminar</button> : null}</div></article>;
}
