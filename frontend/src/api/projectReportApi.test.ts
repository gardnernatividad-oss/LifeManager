import { describe, expect, it, vi } from "vitest";
import { apiClient } from "./client";
import { getProjectReport } from "./projectReportApi";

vi.mock("./client", () => ({ apiClient: { get: vi.fn() } }));

describe("projectReportApi", () => {
  it("uses the exact endpoint and filter params without workspace_id", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: {} });
    const params = {
      planned_from: "2026-08-01",
      planned_to: "2026-08-31",
      category_id: "category-id",
      is_active: true,
      state: "EN_PROCESO" as const,
    };
    await getProjectReport(params);
    expect(apiClient.get).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/reports/projects",
      { params },
    );
    expect(params).not.toHaveProperty("workspace_id");
  });
});
