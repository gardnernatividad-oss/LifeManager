import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "./client";
import { getHomeSummary, getV2HomeSummary } from "./homeApi";
import type { HomeSummary } from "../types/home";

vi.mock("./client", () => ({ apiClient: { get: vi.fn() } }));

const summary: HomeSummary = {
  user_first_name: "Ana",
  local_date: "2026-08-13",
  tasks: { due_today: 1, overdue: 2 },
  pending_items: { overdue: 3 },
  project_steps: { overdue: 4 },
  last_review_saved_at: null,
  pending_items_last_tracking_saved_at: null
};

describe("homeApi", () => {
  beforeEach(() => vi.clearAllMocks());

  it("requests the versioned Home endpoint without Workspace parameters", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: summary });
    await expect(getHomeSummary()).resolves.toEqual(summary);
    expect(apiClient.get).toHaveBeenCalledWith("http://localhost:3000/api/v1/home");
    expect(apiClient.get).toHaveBeenCalledTimes(1);
  });

  it("requests the global V2 Home projection without Workspace parameters", async () => {
    const v2Summary = { local_date: "2026-08-30", today: { tasks: 0, pending_items: 0, project_stages: 0, activities: 0 }, upcoming_activities: [], attention: [], upcoming_days: [] };
    vi.mocked(apiClient.get).mockResolvedValue({ data: v2Summary });
    await expect(getV2HomeSummary()).resolves.toEqual(v2Summary);
    expect(apiClient.get).toHaveBeenCalledWith("http://localhost:3000/api/v2/home");
  });
});
