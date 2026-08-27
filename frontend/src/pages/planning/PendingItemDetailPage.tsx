import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useState, type FormEvent } from "react";
import { queryKeys } from "../../api/queryKeys";
import { correctV2PendingItem, deactivateV2PendingItem, deleteV2PendingItem, getV2PendingItem, listV2PendingItemHistory, reactivateV2PendingItem, updateV2PendingItemProgress } from "../../api/v2PendingItemApi";
import { useAuth } from "../../hooks/useAuth";
import { formatShortCalendarDate } from "../../utils/localizedDate";

const mutationError = (error: unknown) => axios.isAxiosError(error) && error.response?.status === 409
  ? "El Pendiente cambió. Actualizamos el detalle; vuelve a intentarlo."
  : "No pudimos guardar el cambio.";

export function PendingItemDetailPage() {
  const { workspace } = useAuth();
  const { pendingItemId = "" } = useParams();
  if (!workspace || !pendingItemId) return <section><h1>Detalle del Pendiente</h1><p>Selecciona un espacio.</p></section>;
  return <WorkspacePendingDetail key={`${workspace.id}:${pendingItemId}`} workspaceId={workspace.id} pendingItemId={pendingItemId} />;
}

function WorkspacePendingDetail({ workspaceId, pendingItemId }: { workspaceId: string; pendingItemId: string }) {
  const client = useQueryClient();
  const navigate = useNavigate();
  const [comment, setComment] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const detail = useQuery({ queryKey: queryKeys.v2PendingItemDetail(workspaceId, pendingItemId), queryFn: () => getV2PendingItem(workspaceId, pendingItemId) });
  const history = useQuery({ queryKey: queryKeys.v2PendingItemHistory(workspaceId, pendingItemId), queryFn: () => listV2PendingItemHistory(workspaceId, pendingItemId) });
  const refresh = async () => Promise.all([
    client.invalidateQueries({ queryKey: queryKeys.v2PendingItemDetail(workspaceId, pendingItemId) }),
    client.invalidateQueries({ queryKey: queryKeys.v2PendingItemHistory(workspaceId, pendingItemId) }),
    client.invalidateQueries({ queryKey: queryKeys.v2PendingItemsRoot(workspaceId) })
  ]);
  const mutation = useMutation({ mutationFn: (operation: () => Promise<unknown>) => operation(), onSuccess: async () => { setComment(""); setFeedback("Cambio guardado."); await refresh(); }, onError: async (error) => { setFeedback(mutationError(error)); await refresh(); } });

  if (detail.isPending) return <section role="status">Cargando detalle…</section>;
  if (detail.isError) return <section role="alert"><p>No pudimos cargar el Pendiente.</p><Link to="/planificacion/pendientes">← Volver</Link></section>;
  const item = detail.data;

  function submitTracking(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = String(new FormData(event.currentTarget).get("progress") ?? "");
    const cleanedComment = comment.trim();
    if (!value && !cleanedComment) { setFeedback("Ingresa un avance o un comentario."); return; }
    const nextProgress = value ? Number(value) : null;
    mutation.mutate(() => item.can_correct
      ? correctV2PendingItem(workspaceId, item.id, Number(value), item.lock_version, cleanedComment || undefined)
      : updateV2PendingItemProgress(workspaceId, item.id, nextProgress, item.lock_version, cleanedComment || undefined));
  }

  return <section className="pending-detail-page">
    <Link className="pending-detail-back" to="/planificacion/pendientes" aria-label="Volver al registro de Pendientes">← Volver</Link>
    <header><p className="eyebrow">Pendiente</p><h1>{item.name}</h1></header>
    <dl className="pending-detail-summary">
      <div><dt>Avance</dt><dd>{item.progress}%</dd></div><div><dt>Estado</dt><dd>{item.state}</dd></div>
      <div><dt>Vigencia</dt><dd>{item.is_active ? "Activo" : "Inactivo"}</dd></div><div><dt>Fecha planificada</dt><dd>{item.planned_date ? formatShortCalendarDate(item.planned_date) : "—"}</dd></div>
      <div><dt>Cumplimiento</dt><dd>{item.compliance ?? "—"}</dd></div><div><dt>Detalle de cumplimiento</dt><dd>{item.compliance_detail_days === null ? "—" : `${item.compliance_detail_days} día(s)`}</dd></div>
      <div><dt>Fecha de cumplimiento</dt><dd>{item.completion_date ? formatShortCalendarDate(item.completion_date) : "—"}</dd></div><div><dt>Categoría</dt><dd>{item.category_name}</dd></div>
      <div><dt>Responsable</dt><dd>{item.responsible_display_name}</dd></div>
    </dl>
    <div className="pending-detail-actions">{item.can_edit ? <Link className="secondary-button" to="/planificacion/pendientes">Editar planificación</Link> : null}{item.can_deactivate ? <button type="button" disabled={mutation.isPending} onClick={() => mutation.mutate(() => deactivateV2PendingItem(workspaceId, item.id, item.lock_version))}>Desactivar</button> : null}{item.can_reactivate ? <form onSubmit={(event) => { event.preventDefault(); const plannedDate = String(new FormData(event.currentTarget).get("planned_date")); mutation.mutate(() => reactivateV2PendingItem(workspaceId, item.id, plannedDate, item.lock_version)); }}><label>Nueva fecha planificada<input name="planned_date" type="date" required /></label><button disabled={mutation.isPending}>Reactivar</button></form> : null}{item.can_delete ? <button type="button" disabled={mutation.isPending} onClick={() => { if (window.confirm(`¿Eliminar ${item.name}?`)) mutation.mutate(() => deleteV2PendingItem(workspaceId, item.id, item.lock_version).then(() => navigate("/planificacion/pendientes"))); }}>Eliminar</button> : null}</div>
    {item.can_update_progress || item.can_correct ? <section className="pending-detail-tracking"><h2>{item.can_correct ? "Corrección" : "Seguimiento"}</h2>{item.can_correct ? <p>La corrección reabrirá el Pendiente y conservará su historial.</p> : null}<form onSubmit={submitTracking}><label>{item.can_correct ? "Nuevo avance" : "Avance (opcional)"}<input name="progress" type="number" min="0" max={item.can_correct ? 99 : 100} required={item.can_correct} /></label><label>Comentario (opcional)<textarea maxLength={2000} value={comment} onChange={(event) => setComment(event.target.value)} /></label><button disabled={mutation.isPending}>Guardar seguimiento</button></form></section> : null}
    {feedback ? <p className="review-notice" role="status">{feedback}</p> : null}
    <section className="pending-history"><h2>Historial</h2>{history.isPending ? <p role="status">Cargando historial…</p> : history.isError ? <div role="alert"><p>No pudimos cargar el historial.</p><button type="button" onClick={() => void history.refetch()}>Reintentar</button></div> : history.data.items.length === 0 ? <p>Sin registros todavía.</p> : <ol>{history.data.items.map((entry) => <li key={entry.id}><div><strong>{entry.type === "CORRECTION" ? "Corrección" : "Seguimiento"}</strong><time dateTime={entry.recorded_at}>{new Intl.DateTimeFormat("es-PE", { dateStyle: "short", timeStyle: "short" }).format(new Date(entry.recorded_at))}</time></div><p>{entry.actor_display_name} · {entry.progress}%</p>{entry.comment ? <p className="pending-history-comment">{entry.comment}</p> : null}</li>)}</ol>}</section>
  </section>;
}
