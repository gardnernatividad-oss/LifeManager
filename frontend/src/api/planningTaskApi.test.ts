import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "./client";
import * as api from "./planningTaskApi";

vi.mock("./client", () => ({ apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }));

describe("planningTaskApi", () => {
  beforeEach(() => vi.clearAllMocks());
  it("loads every MasterTask page in batches of 100 without Workspace parameters", async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: { items: [{ id: "one" }], total: 101, page: 1, page_size: 100, total_pages: 2 } }).mockResolvedValueOnce({ data: { items: [{ id: "two" }], total: 101, page: 2, page_size: 100, total_pages: 2 } });
    await expect(api.listAllMasterTasks()).resolves.toEqual([{ id: "one" }, { id: "two" }]);
    expect(apiClient.get).toHaveBeenNthCalledWith(1, "http://localhost:8000/api/v1/master-tasks", { params: { page: 1, page_size: 100 } });
    expect(apiClient.get).toHaveBeenNthCalledWith(2, "http://localhost:8000/api/v1/master-tasks", { params: { page: 2, page_size: 100 } });
  });
  it("uses exact target Task endpoints and payloads", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: {} }); vi.mocked(apiClient.patch).mockResolvedValue({ data: {} }); vi.mocked(apiClient.delete).mockResolvedValue({});
    await api.createPlanningTask({ master_task_id: "master", planned_date: "2026-08-20" });
    expect(apiClient.post).toHaveBeenCalledWith("http://localhost:8000/api/v1/tasks", { master_task_id: "master", planned_date: "2026-08-20" });
    await api.createPlanningTasksBulk({ master_task_id: "master", start_date: "2026-08-20", end_date: "2026-08-30", pattern: "WEEKLY", weekdays: [0, 2] });
    expect(apiClient.post).toHaveBeenCalledWith("http://localhost:8000/api/v1/tasks/bulk", expect.objectContaining({ weekdays: [0, 2] }));
    await api.updatePlanningTask("task", { planned_date: "2026-08-21", lock_version: 3 });
    expect(apiClient.patch).toHaveBeenCalledWith("http://localhost:8000/api/v1/tasks/task", { planned_date: "2026-08-21", lock_version: 3 });
    await api.deletePlanningTask("task", 3);
    expect(apiClient.delete).toHaveBeenCalledWith("http://localhost:8000/api/v1/tasks/task", { params: { lock_version: 3 } });
    await api.deletePlanningTasksBulk([{ id: "task", lock_version: 3 }]);
    expect(apiClient.post).toHaveBeenCalledWith("http://localhost:8000/api/v1/tasks/bulk-delete", { items: [{ id: "task", lock_version: 3 }] });
  });
});
