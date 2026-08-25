import { useQuery } from "@tanstack/react-query";

import { listV2CatalogSelector, type CatalogSelectorKind } from "../api/v2CatalogApi";
import { queryKeys } from "../api/queryKeys";

export function useV2CatalogSelector(workspaceId: string, kind: CatalogSelectorKind, currentId?: string, search?: string) {
  return useQuery({
    queryKey: queryKeys.v2CatalogSelector(workspaceId, kind, currentId, search),
    queryFn: () => listV2CatalogSelector(workspaceId, kind, currentId, search),
    enabled: Boolean(workspaceId),
  });
}
