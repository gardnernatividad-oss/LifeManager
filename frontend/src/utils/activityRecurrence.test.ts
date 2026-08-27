import { describe, expect, it } from "vitest";
import { activityRecurrenceDates } from "./activityRecurrence";

describe("activityRecurrenceDates", () => {
  it("expands daily and Monday-based weekly dates", () => {
    expect(activityRecurrenceDates({ pattern: "DAILY", dateFrom: "2028-02-28", dateUntil: "2028-03-01" })).toEqual(["2028-02-28", "2028-02-29", "2028-03-01"]);
    expect(activityRecurrenceDates({ pattern: "WEEKLY", dateFrom: "2027-01-04", dateUntil: "2027-01-10", weekdays: [0, 6] })).toEqual(["2027-01-04", "2027-01-10"]);
  });
  it("falls back monthly and deduplicates converging dates", () => {
    expect(activityRecurrenceDates({ pattern: "MONTHLY", dateFrom: "2027-02-01", dateUntil: "2027-02-28", monthDays: [29, 30, 31] })).toEqual(["2027-02-28"]);
  });
});
