import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "./client";
import { createV2RecurringTasks, createV2Task, deleteV2Task, listV2Tasks, resolveV2Task, updateV2Task } from "./v2TaskApi";

vi.mock("./client", () => ({ apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }));
describe("v2TaskApi", () => {
  beforeEach(() => vi.clearAllMocks());
  it("uses only workspace-scoped V2 Task routes", async () => { vi.mocked(apiClient.get).mockResolvedValue({ data: { items: [], total: 0, page: 1, page_size: 25, total_pages: 0 } }); await listV2Tasks("workspace-a", { page: 1, page_size: 25 }); expect(apiClient.get).toHaveBeenCalledWith(expect.stringContaining("/api/v2/workspaces/workspace-a/tasks"), { params: { page: 1, page_size: 25 } }); });
  it("sends explicit mutation contracts", async () => { vi.mocked(apiClient.post).mockResolvedValue({ data: {} }); vi.mocked(apiClient.patch).mockResolvedValue({ data: {} }); vi.mocked(apiClient.delete).mockResolvedValue({ data: {} }); await createV2Task("w", { master_task_id: "m", planned_date: "2026-08-26" }); await updateV2Task("w", "t", { planned_date: "2026-08-27", lock_version: 2 }); await resolveV2Task("w", "t", "NOT_COMPLETED", 3); await deleteV2Task("w", "t", 4); expect(apiClient.post).toHaveBeenLastCalledWith(expect.stringContaining("/t/not-complete"), { lock_version: 3 }); expect(apiClient.delete).toHaveBeenCalledWith(expect.stringContaining("/tasks/t"), { params: { lock_version: 4 } }); });
  it("posts the strict finite recurrence contract", async () => { vi.mocked(apiClient.post).mockResolvedValue({ data: { created_count: 2, items: [] } }); const payload = { master_task_id: "m", recurrence: { pattern: "WEEKLY" as const, date_from: "2026-08-17", date_until: "2026-08-23", weekdays: [0, 2] } }; await createV2RecurringTasks("w", payload); expect(apiClient.post).toHaveBeenCalledWith(expect.stringContaining("/api/v2/workspaces/w/tasks/recurring"), payload); });
});
