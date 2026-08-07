import { describe, expect, it } from "vitest";

import { isoToLocalInput, localDateTimeToIso } from "./taskDateTime";

describe("Task date/time conversion", () => {
  it("converts a normal America/Lima wall time to UTC", () => {
    expect(localDateTimeToIso("2026-08-08T10:30", "America/Lima"))
      .toBe("2026-08-08T15:30:00.000Z");
  });

  it("converts a normal date in a timezone that observes daylight saving", () => {
    expect(localDateTimeToIso("2026-07-01T10:30", "America/New_York"))
      .toBe("2026-07-01T14:30:00.000Z");
  });

  it("rejects a nonexistent spring-forward wall time", () => {
    expect(() => localDateTimeToIso("2026-03-08T02:30", "America/New_York"))
      .toThrow("La hora seleccionada no existe en la zona horaria del espacio.");
  });

  it("rejects an ambiguous fall-back wall time", () => {
    expect(() => localDateTimeToIso("2026-11-01T01:30", "America/New_York"))
      .toThrow("La hora seleccionada es ambigua por un cambio de horario en la zona del espacio. Elige otra hora.");
  });

  it("converts an ISO instant to the Workspace local display input", () => {
    expect(isoToLocalInput("2026-07-01T14:30:00.000Z", "America/New_York"))
      .toBe("2026-07-01T10:30");
  });
});
