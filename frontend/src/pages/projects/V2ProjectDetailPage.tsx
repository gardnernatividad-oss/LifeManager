import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { getV2Project } from "../../api/v2ProjectApi";
import { queryKeys } from "../../api/queryKeys";
import { listWorkspaceMembers } from "../../api/workspaceApi";
import { useAuth } from "../../hooks/useAuth";
import { formatShortCalendarDate } from "../../utils/localizedDate";
import { ProjectStagesPanel } from "../planning/ProjectStagesPanel";

const labels: Record<string, string> = { NO_INICIADO: "No iniciado", EN_PROCESO: "En proceso", FINALIZADO: "Finalizado", CONFIGURACION_INCOMPLETA: "Configuración incompleta", EN_PLAZO: "En plazo", ATRASADO: "Atrasado", A_TIEMPO: "A tiempo", CON_ADELANTO: "Con adelanto", CON_RETRASO: "Con retraso" };

export function V2ProjectDetailPage({ mode }: { mode: "planning" | "tracking" }) {
  const { workspace } = useAuth();
  const { projectId } = useParams();
  if (!workspace || !projectId) return <section><h1>Proyecto</h1><p>Selecciona un espacio y un Proyecto.</p></section>;
  return <WorkspaceProjectDetail key={`${workspace.id}:${projectId}`} workspaceId={workspace.id} shared={workspace.kind === "SHARED"} projectId={projectId} mode={mode} />;
}

function WorkspaceProjectDetail({ workspaceId, shared, projectId, mode }: { workspaceId: string; shared: boolean; projectId: string; mode: "planning" | "tracking" }) {
  const project = useQuery({ queryKey: queryKeys.v2ProjectDetail(workspaceId, projectId), queryFn: () => getV2Project(workspaceId, projectId) });
  const members = useQuery({ queryKey: queryKeys.workspaceMembers(workspaceId), queryFn: () => listWorkspaceMembers(workspaceId), enabled: shared && mode === "planning" });
  const basePath = mode === "planning" ? "/planificacion/proyectos" : "/seguimiento/proyectos";
  if (project.isPending) return <p role="status">Cargando Proyecto…</p>;
  if (project.isError) return <section role="alert"><p>No pudimos cargar el Proyecto.</p><Link to={basePath}>Volver a Proyectos</Link></section>;
  const item = project.data;
  return <section className="project-detail-page">
    <Link className="back-link" to={basePath}>← Volver a Proyectos</Link>
    <header><p className="eyebrow">{mode === "planning" ? "Planificación" : "Seguimiento"} · Proyecto</p><h1>{item.name}</h1><p>{item.description || "Sin descripción"}</p></header>
    <dl className="project-detail-grid">
      <div><dt>Vigencia</dt><dd>{item.is_active ? "Activo" : "Inactivo"}</dd></div><div><dt>Categoría</dt><dd>{item.category_name}</dd></div><div><dt>Líder</dt><dd>{item.leader_display_name}</dd></div>
      <div><dt>Fecha planificada</dt><dd>{item.planned_date ? formatShortCalendarDate(item.planned_date) : "—"}</dd></div><div><dt>Avance</dt><dd>{item.progress === null ? "—" : `${item.progress}%`}</dd></div><div><dt>Estado</dt><dd>{item.state ? labels[item.state] ?? item.state : "—"}</dd></div>
      <div><dt>Cumplimiento</dt><dd>{item.compliance ? labels[item.compliance] ?? item.compliance : "—"}</dd></div><div><dt>Detalle</dt><dd>{item.compliance_detail_days === null ? "—" : `${item.compliance_detail_days} días`}</dd></div><div><dt>Fecha de cumplimiento</dt><dd>{item.completion_date ? formatShortCalendarDate(item.completion_date) : "—"}</dd></div>
    </dl>
    <p className={item.weights_complete ? "stage-weight-summary" : "stage-weight-summary stage-weight-summary--incomplete"}>{item.weights_complete ? "Configuración de pesos completa." : `Configuración de pesos incompleta: ${item.total_weight}% de 100%.`}</p>
    <ProjectStagesPanel workspaceId={workspaceId} project={item} shared={shared} members={(members.data ?? []).filter((member) => member.status === "ACTIVE")} basePath={basePath} editable={mode === "planning"} />
  </section>;
}
