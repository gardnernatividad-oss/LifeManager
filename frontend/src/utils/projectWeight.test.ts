import { describe, expect, it } from "vitest";
import { totalWeightHundredths, weightToHundredths } from "./projectWeight";
describe("Project weights", () => {
  it("uses exact integer hundredths", () => { expect(weightToHundredths("25")).toBe(2500); expect(weightToHundredths("25.5")).toBe(2550); expect(weightToHundredths("25.50")).toBe(2550); expect(totalWeightHundredths([{ weight: "33.33" }, { weight: "33.33" }, { weight: "33.34" }])).toBe(10000); });
  it("rejects invalid backend precision", () => { expect(weightToHundredths("0")).toBeNull(); expect(weightToHundredths("1.001")).toBeNull(); expect(weightToHundredths("100.01")).toBeNull(); });
});
