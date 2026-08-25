import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { queryKeys } from "../api/queryKeys";
import { listWorkspaces } from "../api/workspaceApi";
import { useAuth } from "./useAuth";

const WORKSPACE_PREFERENCE_KEY = "lifemanager.selected-workspace-id";

export function useWorkspaces() {
  const { isAuthenticated, setWorkspace, workspace } = useAuth();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: queryKeys.workspaces,
    queryFn: listWorkspaces,
    enabled: isAuthenticated,
    staleTime: 60_000
  });

  useEffect(() => {
    if (!query.data) return;

    if (query.data.length === 0) {
      window.localStorage.removeItem(WORKSPACE_PREFERENCE_KEY);
      if (workspace) {
        setWorkspace(null);
        queryClient.removeQueries({
          predicate: (cached) => !["home", "review", "workspaces", "workspace-invitations"].includes(String(cached.queryKey[0])),
        });
      }
      return;
    }

    const preferredId = window.localStorage.getItem(WORKSPACE_PREFERENCE_KEY);
    const selectedWorkspace = workspace
      ? query.data.find((candidate) => candidate.id === workspace.id)
      : query.data.find((candidate) => candidate.id === preferredId);
    const personalWorkspace = query.data.find((candidate) => candidate.kind === "PERSONAL");
    const effectiveWorkspace = selectedWorkspace ?? personalWorkspace ?? query.data[0];

    if (
      !workspace ||
      workspace.id !== effectiveWorkspace.id ||
      workspace.name !== effectiveWorkspace.name
    ) {
      if (workspace && workspace.id !== effectiveWorkspace.id) {
        queryClient.removeQueries({
          predicate: (cached) => !["home", "review", "workspaces", "workspace-invitations"].includes(String(cached.queryKey[0])),
        });
      }
      setWorkspace(effectiveWorkspace);
    }
    window.localStorage.setItem(WORKSPACE_PREFERENCE_KEY, effectiveWorkspace.id);
  }, [query.data, queryClient, setWorkspace, workspace]);

  return query;
}
