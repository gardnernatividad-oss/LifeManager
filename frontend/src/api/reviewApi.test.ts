import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "./client";
import { getReview, saveReview } from "./reviewApi";
import type { ReviewRead, ReviewSave } from "../types/review";

vi.mock("./client", () => ({ apiClient: { get: vi.fn(), patch: vi.fn() } }));

const review: ReviewRead = {
  review_date: "2026-08-13",
  last_review_saved_at: null,
  tasks: [],
  pending_items: [],
  projects: []
};

describe("reviewApi", () => {
  beforeEach(() => vi.clearAllMocks());

  it("gets Review without a Workspace parameter", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: review });
    await expect(getReview()).resolves.toEqual(review);
    expect(apiClient.get).toHaveBeenCalledWith("http://localhost:8000/api/v1/review");
  });

  it("patches only the strict Review sections", async () => {
    const payload: ReviewSave = {
      tasks: [{ id: "task-id", result: "COMPLETED", lock_version: 2 }],
      pending_items: [{ id: "pending-id", progress: 50, lock_version: 3 }],
      project_steps: [{ id: "step-id", comment: "Listo", lock_version: 4 }]
    };
    vi.mocked(apiClient.patch).mockResolvedValue({ data: { saved_at: "2026-08-13T20:00:00Z" } });
    await saveReview(payload);
    expect(apiClient.patch).toHaveBeenCalledWith("http://localhost:8000/api/v1/review", payload);
    expect(JSON.stringify(payload)).not.toContain("workspace_id");
    expect(JSON.stringify(payload)).not.toContain("review_date");
  });
});
