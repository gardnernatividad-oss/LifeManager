import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import { queryKeys } from "../api/queryKeys";
import { listWorkspaces } from "../api/workspaceApi";
import { useAuth } from "./useAuth";

export function useWorkspaces() {
  const { isAuthenticated, setWorkspace, workspace } = useAuth();
  const query = useQuery({
    queryKey: queryKeys.workspaces,
    queryFn: listWorkspaces,
    enabled: isAuthenticated,
    staleTime: 60_000
  });

  useEffect(() => {
    if (!query.data) return;

    if (query.data.length === 0) {
      if (workspace) setWorkspace(null);
      return;
    }

    const selectedWorkspace = workspace
      ? query.data.find((candidate) => candidate.id === workspace.id)
      : undefined;
    const effectiveWorkspace = selectedWorkspace ?? query.data[0];

    if (
      !workspace ||
      workspace.id !== effectiveWorkspace.id ||
      workspace.name !== effectiveWorkspace.name
    ) {
      setWorkspace(effectiveWorkspace);
    }
  }, [query.data, setWorkspace, workspace]);

  return query;
}
