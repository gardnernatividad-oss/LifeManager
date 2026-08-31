import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "./client";
import { listWorkspaces } from "./workspaceApi";

vi.mock("./client", () => ({ apiClient: { get: vi.fn() } }));

describe("V2 Workspace API", () => {
  beforeEach(() => vi.clearAllMocks());

  it("loads the membership-scoped listing through the V2 route without V1 fallback", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [] });

    await expect(listWorkspaces()).resolves.toEqual([]);

    expect(apiClient.get).toHaveBeenCalledWith("http://localhost:3000/api/v2/workspaces");
    expect(apiClient.get).not.toHaveBeenCalledWith(expect.stringContaining("/api/v1/workspaces"));
  });
});
