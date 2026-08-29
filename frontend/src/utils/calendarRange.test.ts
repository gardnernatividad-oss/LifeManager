import { describe, expect, it } from "vitest";
import { calendarRange, mondayOfWeek } from "./calendarRange";

describe("calendarRange", () => {
  it("starts weeks on Monday and creates local-time ranges", () => {
    expect(mondayOfWeek("2027-01-06")).toBe("2027-01-04");
    expect(calendarRange("2027-01-06", "WEEK", "America/Lima")).toEqual({ first: "2027-01-04", after: "2027-01-11", from: "2027-01-04T05:00:00.000Z", to: "2027-01-11T05:00:00.000Z" });
  });
  it("uses complete local calendar months, including DST zones", () => {
    expect(calendarRange("2027-03-15", "MONTH", "America/New_York")).toEqual({
      first: "2027-03-01", after: "2027-04-01",
      from: "2027-03-01T05:00:00.000Z", to: "2027-04-01T04:00:00.000Z",
    });
  });
});
