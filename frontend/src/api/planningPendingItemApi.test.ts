import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "./client";
import * as api from "./planningPendingItemApi";

vi.mock("./client", () => ({ apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }));

describe("planningPendingItemApi", () => {
  beforeEach(() => vi.clearAllMocks());

  it("loads and concatenates every Category page sequentially without Workspace parameters", async () => {
    let releaseSecondPage!: () => void;
    const secondPageGate = new Promise<void>((resolve) => { releaseSecondPage = resolve; });
    vi.mocked(apiClient.get)
      .mockResolvedValueOnce({ data: { items: [{ id: "one", name: "Casa" }], total: 201, page: 1, page_size: 100, total_pages: 3 } })
      .mockImplementationOnce(async () => {
        await secondPageGate;
        return { data: { items: [{ id: "two", name: "Salud" }], total: 201, page: 2, page_size: 100, total_pages: 3 } };
      })
      .mockResolvedValueOnce({ data: { items: [{ id: "three", name: "Trabajo" }], total: 201, page: 3, page_size: 100, total_pages: 3 } });

    const result = api.listAllCategoryOptions();
    await vi.waitFor(() => expect(apiClient.get).toHaveBeenCalledTimes(2));
    expect(apiClient.get).not.toHaveBeenCalledWith("http://localhost:3000/api/v1/categories", { params: { page: 3, page_size: 100 } });
    releaseSecondPage();

    await expect(result).resolves.toEqual([{ id: "one", name: "Casa" }, { id: "two", name: "Salud" }, { id: "three", name: "Trabajo" }]);
    expect(apiClient.get).toHaveBeenNthCalledWith(1, "http://localhost:3000/api/v1/categories", { params: { page: 1, page_size: 100 } });
    expect(apiClient.get).toHaveBeenNthCalledWith(2, "http://localhost:3000/api/v1/categories", { params: { page: 2, page_size: 100 } });
    expect(apiClient.get).toHaveBeenNthCalledWith(3, "http://localhost:3000/api/v1/categories", { params: { page: 3, page_size: 100 } });
  });

  it("uses the exact Pending Item endpoints and payloads", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { items: [] } });
    vi.mocked(apiClient.post).mockResolvedValue({ data: {} });
    vi.mocked(apiClient.patch).mockResolvedValue({ data: {} });

    const params = { page: 1, page_size: 25, is_active: true, category_id: "category", planned_from: "2026-08-01", planned_to: "2026-08-31" };
    await api.listPlanningPendingItems(params);
    expect(apiClient.get).toHaveBeenCalledWith("http://localhost:3000/api/v1/pending-items", { params });

    const createPayload = { category_id: "category", name: "Renovar documento", is_active: true, planned_date: "2026-08-20" };
    await api.createPlanningPendingItem(createPayload);
    expect(apiClient.post).toHaveBeenCalledWith("http://localhost:3000/api/v1/pending-items", createPayload);
    expect(createPayload).not.toHaveProperty("workspace_id");

    const updatePayload = { category_id: "category", name: "Renovar DNI", is_active: false, planned_date: null, lock_version: 4 };
    await api.updatePlanningPendingItem("pending", updatePayload);
    expect(apiClient.patch).toHaveBeenCalledWith("http://localhost:3000/api/v1/pending-items/pending", updatePayload);
  });
});
