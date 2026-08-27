import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { getV2Project } from "../../api/v2ProjectApi";
import { getV2ProjectStage, listV2ProjectStageHistory, updateV2ProjectStageProgress } from "../../api/v2ProjectStageApi";
import { queryKeys } from "../../api/queryKeys";
import { useAuth } from "../../hooks/useAuth";
import { formatShortCalendarDate } from "../../utils/localizedDate";

const labels: Record<string, string> = { NO_INICIADA: "No iniciada", EN_PROCESO: "En proceso", FINALIZADA: "Finalizada", EN_PLAZO: "En plazo", ATRASADO: "Atrasada", A_TIEMPO: "A tiempo", CON_ADELANTO: "Con adelanto", CON_RETRASO: "Con retraso", TRACKING: "Seguimiento", CORRECTION: "Corrección" };

export function V2ProjectStageDetailPage({ mode }: { mode: "planning" | "tracking" }) {
  const { workspace } = useAuth(); const { projectId, stageId } = useParams();
  if (!workspace || !projectId || !stageId) return <section><h1>Etapa</h1><p>No se encontró la jerarquía solicitada.</p></section>;
  return <WorkspaceStageDetail key={`${workspace.id}:${projectId}:${stageId}`} workspaceId={workspace.id} projectId={projectId} stageId={stageId} mode={mode} />;
}

function WorkspaceStageDetail({ workspaceId, projectId, stageId, mode }: { workspaceId: string; projectId: string; stageId: string; mode: "planning" | "tracking" }) {
  const client = useQueryClient(); const [progress, setProgress] = useState(""); const [comment, setComment] = useState(""); const [feedback, setFeedback] = useState<string | null>(null);
  const project = useQuery({ queryKey: queryKeys.v2ProjectDetail(workspaceId, projectId), queryFn: () => getV2Project(workspaceId, projectId) });
  const stageQuery = useQuery({ queryKey: queryKeys.v2ProjectStageDetail(workspaceId, projectId, stageId), queryFn: () => getV2ProjectStage(workspaceId, projectId, stageId) });
  const history = useQuery({ queryKey: queryKeys.v2ProjectStageHistory(workspaceId, projectId, stageId), queryFn: () => listV2ProjectStageHistory(workspaceId, projectId, stageId) });
  const stage = stageQuery.data;
  const mutation = useMutation({ mutationFn: () => updateV2ProjectStageProgress(workspaceId, projectId, stageId, { ...(progress === "" ? {} : { progress: Number(progress) }), ...(comment.trim() ? { comment: comment.trim() } : {}), lock_version: stage!.lock_version, project_lock_version: project.data!.lock_version }), onSuccess: async () => { setProgress(""); setComment(""); setFeedback("Seguimiento guardado."); await Promise.all([client.invalidateQueries({ queryKey: queryKeys.v2ProjectStages(workspaceId, projectId) }), client.invalidateQueries({ queryKey: queryKeys.v2ProjectStageDetail(workspaceId, projectId, stageId) }), client.invalidateQueries({ queryKey: queryKeys.v2ProjectStageHistory(workspaceId, projectId, stageId) }), client.invalidateQueries({ queryKey: queryKeys.v2ProjectDetail(workspaceId, projectId) }), client.invalidateQueries({ queryKey: queryKeys.v2ProjectsRoot(workspaceId) })]); }, onError: async (error) => { setFeedback(axios.isAxiosError(error) && error.response?.status === 409 ? "La Etapa cambió o ya está finalizada. Actualizamos los datos." : "No pudimos guardar el seguimiento."); await Promise.all([stageQuery.refetch(), project.refetch(), history.refetch()]); } });
  const basePath = mode === "planning" ? "/planificacion/proyectos" : "/seguimiento/proyectos";
  function submit(event: FormEvent) { event.preventDefault(); if (progress === "" && !comment.trim()) { setFeedback("Ingresa un avance o un comentario."); return; } mutation.mutate(); }
  if (project.isPending || stageQuery.isPending) return <p role="status">Cargando Etapa…</p>;
  if (project.isError || stageQuery.isError || !stage) return <section role="alert"><p>No pudimos cargar la Etapa.</p><Link to={`${basePath}/${projectId}`}>Volver al Proyecto</Link></section>;
  return <section className="project-stage-detail-page"><Link className="back-link" to={`${basePath}/${projectId}`}>← Volver al Proyecto</Link><header><p className="eyebrow">{project.data.name} · Etapa</p><h1>{stage.name}</h1></header>
    <dl className="project-detail-grid"><div><dt>Responsable</dt><dd>{stage.responsible_display_name}</dd></div><div><dt>Peso</dt><dd>{stage.weight}%</dd></div><div><dt>Fecha planificada</dt><dd>{formatShortCalendarDate(stage.planned_date)}</dd></div><div><dt>Avance</dt><dd>{stage.progress}%</dd></div><div><dt>Estado</dt><dd>{labels[stage.state]}</dd></div><div><dt>Cumplimiento</dt><dd>{labels[stage.compliance]}</dd></div><div><dt>Detalle</dt><dd>{stage.compliance_detail_days} días</dd></div><div><dt>Fecha de cumplimiento</dt><dd>{stage.completion_date ? formatShortCalendarDate(stage.completion_date) : "—"}</dd></div></dl>
    <section className="stage-tracking"><h2>Comentarios / Seguimiento</h2>{feedback ? <p role="status">{feedback}</p> : null}{stage.can_update_progress ? <form onSubmit={submit}><label>Nuevo avance (%)<input type="number" min="0" max="100" value={progress} onChange={(event) => setProgress(event.target.value)} placeholder={String(stage.progress)} /></label><label>Comentario<textarea maxLength={2000} value={comment} onChange={(event) => setComment(event.target.value)} /></label><button disabled={mutation.isPending}>Guardar seguimiento</button></form> : <p>La Etapa finalizada es de solo lectura.</p>}</section>
    <section className="pending-history"><h2>Historial</h2>{history.isPending ? <p role="status">Cargando historial…</p> : history.isError ? <div role="alert"><p>No pudimos cargar el historial.</p><button type="button" onClick={() => void history.refetch()}>Reintentar</button></div> : history.data.items.length === 0 ? <p>Sin registros todavía.</p> : <ol>{history.data.items.map((entry) => <li key={entry.id}><div><strong>{labels[entry.type]}</strong><time dateTime={entry.recorded_at}>{new Intl.DateTimeFormat("es-PE", { dateStyle: "short", timeStyle: "short" }).format(new Date(entry.recorded_at))}</time></div><p>{entry.actor_display_name} · {entry.progress}%</p>{entry.comment ? <p className="pending-history-comment">{entry.comment}</p> : null}</li>)}</ol>}</section>
  </section>;
}
