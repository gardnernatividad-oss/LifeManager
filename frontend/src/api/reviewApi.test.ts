import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "./client";
import { getReview, saveReviewPendingItems, saveReviewProjectStages, saveReviewTasks } from "./reviewApi";
import type { ReviewRead } from "../types/review";

vi.mock("./client", () => ({ apiClient: { get: vi.fn(), post: vi.fn() } }));
const review: ReviewRead = { review_date: "2026-08-13", tasks: [], pending_items: [], project_stages: [] };

describe("reviewApi", () => {
  beforeEach(() => vi.clearAllMocks());
  it("gets global Review without a Workspace parameter", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: review });
    await expect(getReview()).resolves.toEqual(review);
    expect(apiClient.get).toHaveBeenCalledWith("http://localhost:3000/api/v2/review");
  });
  it("uses three independent block endpoints and strict payloads", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: { saved_ids: [] } });
    const tasks = { items: [{ task_id: "task-id", result: "COMPLETED" as const, lock_version: 2 }] };
    const pending = { items: [{ pending_item_id: "pending-id", progress: 50, lock_version: 3 }] };
    const stages = { items: [{ stage_id: "stage-id", progress: "45.25", lock_version: 4, project_lock_version: 5 }] };
    await saveReviewTasks(tasks); await saveReviewPendingItems(pending); await saveReviewProjectStages(stages);
    expect(apiClient.post).toHaveBeenNthCalledWith(1, "http://localhost:3000/api/v2/review/tasks", tasks);
    expect(apiClient.post).toHaveBeenNthCalledWith(2, "http://localhost:3000/api/v2/review/pending-items", pending);
    expect(apiClient.post).toHaveBeenNthCalledWith(3, "http://localhost:3000/api/v2/review/project-stages", stages);
    expect(JSON.stringify([tasks, pending, stages])).not.toContain("workspace_id");
  });
});
