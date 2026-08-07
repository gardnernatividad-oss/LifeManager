import { describe, expect, it } from "vitest";

import { getReportPeriodBounds } from "./reportPeriod";

describe("getReportPeriodBounds", () => {
  it("builds month boundaries at local midnight in the Workspace timezone", () => {
    const result = getReportPeriodBounds("this_month", "America/Lima", "", "", new Date("2026-08-15T12:00:00Z"));
    expect(result).toEqual({
      fromDate: "2026-08-01",
      toDate: "2026-08-31",
      scheduledFrom: "2026-08-01T05:00:00.000Z",
      scheduledTo: "2026-09-01T04:59:59.999Z"
    });
  });

  it("uses Monday through Sunday for this week and keeps timezone-aware boundaries", () => {
    const result = getReportPeriodBounds("this_week", "Europe/Madrid", "", "", new Date("2026-08-05T12:00:00Z"));
    expect(result?.fromDate).toBe("2026-08-03");
    expect(result?.toDate).toBe("2026-08-09");
    expect(result?.scheduledFrom).toBe("2026-08-02T22:00:00.000Z");
  });

  it("rejects incomplete or reversed custom periods", () => {
    expect(getReportPeriodBounds("custom", "America/Lima", "", "2026-08-10")).toBeNull();
    expect(getReportPeriodBounds("custom", "America/Lima", "2026-08-11", "2026-08-10")).toBeNull();
  });
});
