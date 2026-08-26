import { describe, expect, it } from "vitest";
import { recurrenceOccurrenceCount } from "./taskRecurrence";

describe("task recurrence preview", () => {
  it("counts inclusive daily and Monday-zero weekly dates", () => {
    expect(recurrenceOccurrenceCount({ pattern: "DAILY", date_from: "2026-09-01", date_until: "2026-09-03" })).toBe(3);
    expect(recurrenceOccurrenceCount({ pattern: "WEEKLY", date_from: "2026-08-17", date_until: "2026-08-23", weekdays: [0, 2] })).toBe(2);
  });
  it("deduplicates monthly fallback collisions", () => {
    expect(recurrenceOccurrenceCount({ pattern: "MONTHLY", date_from: "2027-02-01", date_until: "2027-02-28", month_days: [29, 30, 31] })).toBe(1);
  });
});
