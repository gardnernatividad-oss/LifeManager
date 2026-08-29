import { beforeEach, expect, it, vi } from "vitest";
import { apiClient } from "./client";
import { getCalendarComparison, getCalendarComparisonMulti, getCalendarVisibility, setCalendarVisibility } from "./v2CalendarComparisonApi";

vi.mock("./client", () => ({ apiClient: { get: vi.fn(), patch: vi.fn() } }));

beforeEach(() => { vi.clearAllMocks(); vi.mocked(apiClient.get).mockResolvedValue({ data: {} }); vi.mocked(apiClient.patch).mockResolvedValue({ data: {} }); });

it("uses only the explicit Workspace-scoped comparison contract", async () => {
  await getCalendarComparison("workspace-a", "target-b", "2027-01-01T05:00:00Z", "2027-01-02T05:00:00Z");
  expect(apiClient.get).toHaveBeenCalledWith(expect.stringContaining("/api/v2/workspaces/workspace-a/calendar-comparison"), { params: { target_user_id: "target-b", from: "2027-01-01T05:00:00Z", to: "2027-01-02T05:00:00Z" } });
});

it("sends all selected comparison members through the multi-member contract", async () => {
  await getCalendarComparisonMulti("workspace-a", ["target-b", "target-c"], "2027-01-01T05:00:00Z", "2027-01-02T05:00:00Z");
  expect(apiClient.get).toHaveBeenCalledWith(expect.stringContaining("/calendar-comparison/multi"), expect.objectContaining({ params: expect.objectContaining({ target_user_ids: ["target-b", "target-c"] }) }));
});

it("reads and updates only the authenticated membership visibility", async () => {
  await getCalendarVisibility("workspace-a");
  await setCalendarVisibility("workspace-a", "AVAILABILITY_ONLY", 3);
  expect(apiClient.get).toHaveBeenCalledWith(expect.stringContaining("/api/v2/workspaces/workspace-a/calendar-visibility"));
  expect(apiClient.patch).toHaveBeenCalledWith(expect.stringContaining("/api/v2/workspaces/workspace-a/calendar-visibility"), { visibility: "AVAILABILITY_ONLY", lock_version: 3 });
});
