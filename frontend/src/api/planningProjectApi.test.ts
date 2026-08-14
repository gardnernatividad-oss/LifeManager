import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "./client";
import * as api from "./planningProjectApi";
vi.mock("./client", () => ({ apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }));
describe("planningProjectApi", () => {
  beforeEach(() => vi.clearAllMocks());
  it("uses the exact V1 Project Planning endpoints without workspace_id", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: {} }); vi.mocked(apiClient.post).mockResolvedValue({ data: {} }); vi.mocked(apiClient.patch).mockResolvedValue({ data: {} });
    const params = { page: 1, page_size: 25, is_active: true, category_id: "category", planned_from: "2026-08-01", planned_to: "2026-08-31" };
    await api.listPlanningProjects(params); expect(apiClient.get).toHaveBeenCalledWith("http://localhost:8000/api/v1/projects", { params });
    await api.getPlanningProject("project"); expect(apiClient.get).toHaveBeenCalledWith("http://localhost:8000/api/v1/projects/project");
    const create = { category_id: "category", name: "Mudanza", is_active: true, steps: [{ name: "Empacar", planned_date: "2026-08-20", weight: "100.00", position: 0 }] };
    await api.createPlanningProject(create); expect(apiClient.post).toHaveBeenCalledWith("http://localhost:8000/api/v1/projects", create); expect(create).not.toHaveProperty("workspace_id");
    await api.updatePlanningProject("project", { name: "Mudanza 2", lock_version: 2 }); expect(apiClient.patch).toHaveBeenCalledWith("http://localhost:8000/api/v1/projects/project", { name: "Mudanza 2", lock_version: 2 });
    await api.createPlanningProjectStep("project", create.steps[0]); expect(apiClient.post).toHaveBeenCalledWith("http://localhost:8000/api/v1/projects/project/steps", create.steps[0]);
    await api.updatePlanningProjectStep("project", "step", { position: 1, lock_version: 3 }); expect(apiClient.patch).toHaveBeenCalledWith("http://localhost:8000/api/v1/projects/project/steps/step", { position: 1, lock_version: 3 });
  });
});
