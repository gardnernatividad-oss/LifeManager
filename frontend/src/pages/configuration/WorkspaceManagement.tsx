import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";

import { queryKeys } from "../../api/queryKeys";
import {
  actOnWorkspaceInvitation,
  createSharedWorkspace,
  createWorkspaceInvitation,
  deactivateWorkspace,
  deleteWorkspace,
  leaveWorkspace,
  listManagedWorkspaces,
  listMyWorkspaceInvitations,
  listWorkspaceInvitations,
  listWorkspaceMembers,
  reactivateWorkspace,
  removeWorkspaceMember,
  transferWorkspaceOwnership,
  type MemberExitResolution,
} from "../../api/workspaceApi";
import { useAuth } from "../../hooks/useAuth";
import type { WorkspaceSummary } from "../../types/auth";

function safeMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 403) return "No tienes permisos para realizar esta acción.";
    if (error.response?.status === 404) return "El espacio o recurso ya no está disponible.";
    if (error.response?.status === 409) return "La acción requiere resolver responsabilidades o actualizar el estado.";
  }
  return "No pudimos completar la acción. Intenta nuevamente.";
}

export function WorkspaceManagement() {
  const client = useQueryClient();
  const { user, workspace, setWorkspace } = useAuth();
  const [selectedId, setSelectedId] = useState<string>("");
  const [newName, setNewName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [transferTarget, setTransferTarget] = useState("");
  const [resolutionTarget, setResolutionTarget] = useState<{ userId: string | null } | null>(null);
  const [resolutionMode, setResolutionMode] = useState<"REASSIGN" | "DELETE" | "DELETE_ALL">("REASSIGN");
  const [resolutionUserId, setResolutionUserId] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);

  const management = useQuery({ queryKey: queryKeys.workspaceManagement, queryFn: listManagedWorkspaces });
  const invitations = useQuery({ queryKey: queryKeys.myWorkspaceInvitations, queryFn: listMyWorkspaceInvitations });
  const selected = management.data?.find((item) => item.id === selectedId) ?? null;
  const canLoadDetails = Boolean(selected?.kind === "SHARED" && selected.lifecycle === "ACTIVE");
  const members = useQuery({
    queryKey: queryKeys.workspaceMembers(selected?.id ?? ""),
    queryFn: () => listWorkspaceMembers(selected!.id),
    enabled: canLoadDetails,
  });
  const pendingInvitations = useQuery({
    queryKey: queryKeys.workspaceInvitations(selected?.id ?? ""),
    queryFn: () => listWorkspaceInvitations(selected!.id),
    enabled: canLoadDetails && selected?.visible_role === "Propietario",
  });
  const activeMembers = useMemo(
    () => members.data?.filter((member) => member.status === "ACTIVE") ?? [],
    [members.data],
  );

  async function refreshWorkspaces() {
    await Promise.all([
      client.invalidateQueries({ queryKey: queryKeys.workspaces }),
      client.invalidateQueries({ queryKey: queryKeys.workspaceManagement }),
    ]);
  }

  const action = useMutation({
    mutationFn: async (operation: () => Promise<unknown>) => operation(),
    onSuccess: async () => {
      setFeedback("Acción completada.");
      setResolutionTarget(null);
      await refreshWorkspaces();
      if (selectedId) {
        await Promise.all([
          client.invalidateQueries({ queryKey: queryKeys.workspaceMembers(selectedId) }),
          client.invalidateQueries({ queryKey: queryKeys.workspaceInvitations(selectedId) }),
          client.invalidateQueries({ queryKey: queryKeys.myWorkspaceInvitations }),
        ]);
      }
    },
    onError: (error) => setFeedback(safeMessage(error)),
  });

  function create(event: FormEvent) {
    event.preventDefault();
    const name = newName.trim();
    if (!name) return;
    action.mutate(async () => {
      const created = await createSharedWorkspace(name);
      setNewName("");
      setSelectedId(created.id);
    });
  }

  function resolution(): MemberExitResolution {
    if (resolutionMode === "DELETE_ALL") return { delete_all: true };
    const directive = resolutionMode === "REASSIGN"
      ? { action: "REASSIGN" as const, target_user_id: resolutionUserId }
      : { action: "DELETE" as const };
    return { tasks: directive, pending_items: directive, projects: directive, project_stages: directive };
  }

  function resolveExit() {
    if (!selected || !resolutionTarget) return;
    const payload = resolution();
    action.mutate(() => resolutionTarget.userId
      ? removeWorkspaceMember(selected.id, resolutionTarget.userId, payload)
      : leaveWorkspace(selected.id, payload));
  }

  const active = management.data?.filter((item) => item.lifecycle === "ACTIVE") ?? [];
  const inactive = management.data?.filter((item) => item.lifecycle === "INACTIVE") ?? [];

  return (
    <section className="configuration-panel workspace-management" aria-labelledby="workspace-management-heading">
      <h2 id="workspace-management-heading">Espacios de trabajo</h2>
      <form className="workspace-management__create" onSubmit={create}>
        <label htmlFor="shared-workspace-name">Nuevo espacio compartido</label>
        <input id="shared-workspace-name" maxLength={150} value={newName} onChange={(event) => setNewName(event.target.value)} />
        <button className="primary-button" disabled={action.isPending || !newName.trim()}>Crear</button>
      </form>
      {feedback ? <p role="status" className="review-notice">{feedback}</p> : null}
      {management.isPending ? <p role="status">Cargando espacios…</p> : null}
      {management.isError ? <div role="alert"><p>No pudimos cargar los espacios.</p><button onClick={() => void management.refetch()}>Reintentar</button></div> : null}
      <WorkspaceGroup title="Activos" items={active} selectedId={selectedId} onSelect={setSelectedId} />
      <WorkspaceGroup title="Inactivos" items={inactive} selectedId={selectedId} onSelect={setSelectedId} />

      {selected ? (
        <section className="workspace-management__detail" aria-label={`Administrar ${selected.name}`}>
          <h3>{selected.name}</h3>
          <p>{selected.kind === "PERSONAL" ? "Personal" : "Compartido"} · {selected.visible_role}</p>
          {selected.kind === "PERSONAL" ? <p>El espacio Personal no admite transferencia, salida, desactivación ni eliminación.</p> : null}
          {selected.lifecycle === "INACTIVE" && selected.visible_role === "Propietario" ? (
            <button className="primary-button" onClick={() => action.mutate(() => reactivateWorkspace(selected.id))}>Reactivar Workspace</button>
          ) : null}
          {selected.lifecycle === "ACTIVE" && selected.visible_role === "Propietario" ? (
            <div className="workspace-management__actions">
              {selected.can_delete ? (
                <button onClick={() => window.confirm("¿Eliminar definitivamente este espacio vacío?") && action.mutate(async () => { await deleteWorkspace(selected.id); if (workspace?.id === selected.id) setWorkspace(null); })}>Eliminar Workspace</button>
              ) : (
                <button onClick={() => window.confirm("La desactivación conserva el historial. ¿Continuar?") && action.mutate(() => deactivateWorkspace(selected.id))}>Desactivar Workspace</button>
              )}
            </div>
          ) : null}
          {selected.lifecycle === "ACTIVE" && selected.visible_role === "Miembro" ? (
            <button onClick={() => window.confirm("¿Salir de este Workspace?") && action.mutate(() => leaveWorkspace(selected.id), { onError: (error) => { setFeedback(safeMessage(error)); if (axios.isAxiosError(error) && error.response?.status === 409) setResolutionTarget({ userId: null }); } })}>Salir del Workspace</button>
          ) : null}

          {canLoadDetails && members.isPending ? <p role="status">Cargando miembros…</p> : null}
          {canLoadDetails && members.isError ? <button onClick={() => void members.refetch()}>Reintentar miembros</button> : null}
          {members.data ? <ul className="workspace-management__members">{activeMembers.map((member) => (
            <li key={member.user_id}><span><strong>{member.display_name}</strong> · {member.role}<br /><small>{member.email}</small></span>
              {selected.visible_role === "Propietario" && member.role === "Miembro" ? <button onClick={() => window.confirm(`¿Retirar a ${member.display_name}?`) && action.mutate(() => removeWorkspaceMember(selected.id, member.user_id), { onError: (error) => { setFeedback(safeMessage(error)); if (axios.isAxiosError(error) && error.response?.status === 409) setResolutionTarget({ userId: member.user_id }); } })}>Retirar</button> : null}
            </li>
          ))}</ul> : null}

          {selected.visible_role === "Propietario" && activeMembers.length > 1 ? <div className="workspace-management__inline"><label>Nuevo propietario<select value={transferTarget} onChange={(event) => setTransferTarget(event.target.value)}><option value="">Selecciona</option>{activeMembers.filter((member) => member.role === "Miembro").map((member) => <option key={member.user_id} value={member.user_id}>{member.display_name}</option>)}</select></label><button disabled={!transferTarget} onClick={() => window.confirm("La transferencia cambia tus permisos inmediatamente. ¿Continuar?") && action.mutate(() => transferWorkspaceOwnership(selected.id, transferTarget))}>Transferir propiedad</button></div> : null}

          {selected.visible_role === "Propietario" && selected.lifecycle === "ACTIVE" ? <form className="workspace-management__inline" onSubmit={(event) => { event.preventDefault(); if (inviteEmail.trim()) action.mutate(async () => { await createWorkspaceInvitation(selected.id, inviteEmail.trim()); setInviteEmail(""); }); }}><label>Invitar por correo<input type="email" value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} /></label><button disabled={!inviteEmail.trim()}>Invitar</button></form> : null}
          {pendingInvitations.data?.map((invitation) => <p key={invitation.id}>{invitation.recipient_email} · pendiente <button onClick={() => action.mutate(() => actOnWorkspaceInvitation(invitation.id, "cancel"))}>Cancelar invitación</button></p>)}
        </section>
      ) : null}

      <section aria-labelledby="my-invitations-heading"><h3 id="my-invitations-heading">Mis invitaciones</h3>{invitations.isPending ? <p role="status">Cargando invitaciones…</p> : null}{invitations.isError ? <div role="alert"><p>No pudimos cargar tus invitaciones.</p><button onClick={() => void invitations.refetch()}>Reintentar invitaciones</button></div> : null}{invitations.data?.length === 0 ? <p>No tienes invitaciones pendientes.</p> : invitations.data?.map((invitation) => <div key={invitation.id}><span>{invitation.workspace_name}</span> <button onClick={() => action.mutate(() => actOnWorkspaceInvitation(invitation.id, "accept"))}>Aceptar</button> <button onClick={() => action.mutate(() => actOnWorkspaceInvitation(invitation.id, "reject"))}>Rechazar</button></div>)}</section>

      {resolutionTarget && selected ? <div className="dialog-backdrop"><section className="category-dialog" role="dialog" aria-modal="true" aria-labelledby="resolution-heading"><h2 id="resolution-heading">Resolver responsabilidades futuras</h2><label>Acción<select value={resolutionMode} onChange={(event) => setResolutionMode(event.target.value as typeof resolutionMode)}><option value="REASSIGN">Reasignar</option><option value="DELETE">Eliminar por dominio</option><option value="DELETE_ALL">Eliminar todo</option></select></label>{resolutionMode === "REASSIGN" ? <label>Miembro destino<select value={resolutionUserId} onChange={(event) => setResolutionUserId(event.target.value)}><option value="">Selecciona</option>{activeMembers.filter((member) => member.user_id !== resolutionTarget.userId && member.user_id !== user?.id).map((member) => <option key={member.user_id} value={member.user_id}>{member.display_name}</option>)}</select></label> : null}<div className="dialog-actions"><button onClick={() => setResolutionTarget(null)}>Cancelar</button><button className="primary-button" disabled={resolutionMode === "REASSIGN" && !resolutionUserId} onClick={resolveExit}>Continuar</button></div></section></div> : null}
    </section>
  );
}

function WorkspaceGroup({ title, items, selectedId, onSelect }: { title: string; items: WorkspaceSummary[]; selectedId: string; onSelect: (id: string) => void }) {
  return <section><h3>{title}</h3>{items.length === 0 ? <p className="settings-empty">Sin espacios.</p> : <ul className="workspace-management__list">{items.map((item) => <li key={item.id}><button className={selectedId === item.id ? "workspace-management__workspace workspace-management__workspace--selected" : "workspace-management__workspace"} onClick={() => onSelect(item.id)}><strong>{item.name}</strong><span>{item.kind === "PERSONAL" ? "Personal" : "Compartido"} · {item.visible_role}</span></button></li>)}</ul>}</section>;
}
