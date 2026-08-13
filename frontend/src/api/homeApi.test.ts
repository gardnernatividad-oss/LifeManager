import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "./client";
import { getHomeSummary } from "./homeApi";
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
    expect(apiClient.get).toHaveBeenCalledWith("http://localhost:8000/api/v1/home");
    expect(apiClient.get).toHaveBeenCalledTimes(1);
  });
});
