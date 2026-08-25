import { useQueryClient } from "@tanstack/react-query";

import { queryKeys } from "../../api/queryKeys";
import { useAuth } from "../../hooks/useAuth";
import { useWorkspaces } from "../../hooks/useWorkspaces";

const WORKSPACE_PREFERENCE_KEY = "lifemanager.selected-workspace-id";

export function WorkspaceSelector() {
  const { workspace, setWorkspace } = useAuth();
  const workspaces = useWorkspaces();
  const queryClient = useQueryClient();

  if (workspaces.isPending) {
    return <span className="topbar__workspace-status" role="status">Cargando espacios…</span>;
  }
  if (workspaces.isError) {
    return <button className="secondary-button" type="button" onClick={() => void workspaces.refetch()}>Reintentar espacios</button>;
  }
  if (!workspace || !workspaces.data?.length) return null;

  function selectWorkspace(workspaceId: string) {
    const selected = workspaces.data?.find((candidate) => candidate.id === workspaceId);
    if (!selected || selected.id === workspace?.id) return;
    window.localStorage.setItem(WORKSPACE_PREFERENCE_KEY, selected.id);
    setWorkspace(selected);
    void queryClient.cancelQueries();
    const globalQueryRoots: string[] = [
        queryKeys.workspaces[0],
        queryKeys.home[0],
        queryKeys.review[0],
        queryKeys.myWorkspaceInvitations[0],
      ];
    queryClient.removeQueries({
      predicate: (query) => !globalQueryRoots.includes(String(query.queryKey[0])),
    });
  }

  return (
    <label className="topbar__workspace-control">
      <span className="topbar__label">Espacio</span>
      <select
        className="topbar__workspace-select"
        aria-label="Espacio de trabajo activo"
        value={workspace.id}
        onChange={(event) => selectWorkspace(event.target.value)}
      >
        {workspaces.data.map((candidate) => (
          <option key={candidate.id} value={candidate.id}>
            {candidate.name}{candidate.kind === "PERSONAL" ? " · Personal" : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
