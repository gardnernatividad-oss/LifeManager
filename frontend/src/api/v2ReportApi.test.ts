import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "./client";
import { getV2PendingReport, getV2ProjectReport, getV2ReportSummary, getV2TaskReport } from "./v2ReportApi";

vi.mock("./client", () => ({ apiClient: { get: vi.fn() } }));

describe("V2 Report API", () => {
  beforeEach(() => vi.clearAllMocks());

  it("uses only the workspace-scoped V2 summary contract", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { counts: {} } });
    const filters = { date_from: "2026-08-01", category_id: "category-a" };

    await getV2ReportSummary("workspace-a", filters);

    expect(apiClient.get).toHaveBeenCalledWith(
      "http://localhost:3000/api/v2/workspaces/workspace-a/reports/summary",
      { params: filters },
    );
    expect(apiClient.get).not.toHaveBeenCalledWith(expect.stringContaining("/api/v1/"), expect.anything());
  });

  it("uses the three workspace-scoped V2 detail contracts", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: {} });
    await getV2TaskReport("workspace-a", { custom_tasks: true });
    await getV2PendingReport("workspace-a", {});
    await getV2ProjectReport("workspace-a", {});
    expect(vi.mocked(apiClient.get).mock.calls.map(([url]) => url)).toEqual([
      "http://localhost:3000/api/v2/workspaces/workspace-a/reports/tasks",
      "http://localhost:3000/api/v2/workspaces/workspace-a/reports/pending-items",
      "http://localhost:3000/api/v2/workspaces/workspace-a/reports/projects",
    ]);
  });
});
