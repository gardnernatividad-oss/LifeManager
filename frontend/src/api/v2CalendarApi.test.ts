import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "./client";
import { getMyCalendar } from "./v2CalendarApi";

vi.mock("./client", () => ({ apiClient: { get: vi.fn() } }));

describe("v2CalendarApi", () => {
  beforeEach(() => vi.clearAllMocks());
  it("requests one global authenticated calendar range without Workspace or user id", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { items: [] } });
    await getMyCalendar("2027-01-04T05:00:00Z", "2027-01-11T05:00:00Z");
    expect(apiClient.get).toHaveBeenCalledWith(expect.stringContaining("/api/v2/calendar/me"), { params: { from: "2027-01-04T05:00:00Z", to: "2027-01-11T05:00:00Z", projection: "DETAIL", workspace_id: undefined } });
  });
});
