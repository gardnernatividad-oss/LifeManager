import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "./client";
import { createV2Catalog, listV2Catalog, setV2CatalogActive, updateV2Catalog } from "./v2CatalogApi";

vi.mock("./client", () => ({ apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }));

describe("v2CatalogApi", () => {
  beforeEach(() => vi.clearAllMocks());

  it("keeps every request explicitly scoped to its Workspace", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { items: [], total: 0 } });
    await listV2Catalog("workspace-a", "categories", { active: true, search: "casa" });
    expect(apiClient.get).toHaveBeenCalledWith(expect.stringContaining("/api/v2/workspaces/workspace-a/categories"), { params: { active: true, search: "casa" } });
  });

  it("sends only approved create/update/lifecycle fields", async () => {
    const item = { id: "item", workspace_id: "workspace-a", name: "Casa", is_active: true, lock_version: 3, can_delete: true, created_at: "", updated_at: "" };
    vi.mocked(apiClient.post).mockResolvedValue({ data: item });
    vi.mocked(apiClient.patch).mockResolvedValue({ data: item });
    await createV2Catalog("workspace-a", "categories", { name: "Casa" });
    await updateV2Catalog("workspace-a", "categories", "item", { name: "Hogar", lock_version: 3 });
    await setV2CatalogActive("workspace-a", "categories", item, false);
    expect(apiClient.post).toHaveBeenNthCalledWith(1, expect.any(String), { name: "Casa" });
    expect(apiClient.patch).toHaveBeenCalledWith(expect.stringContaining("/categories/item"), { name: "Hogar", lock_version: 3 });
    expect(apiClient.post).toHaveBeenNthCalledWith(2, expect.stringContaining("/categories/item/deactivate"), { lock_version: 3 });
  });
});
