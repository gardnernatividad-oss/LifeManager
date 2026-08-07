function partsInZone(date: Date, timeZone: string) {
  const values = new Intl.DateTimeFormat("en-CA", {
    timeZone, year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23"
  }).formatToParts(date);
  return Object.fromEntries(values.map((part) => [part.type, part.value]));
}

export function localDateTimeToIso(value: string, timeZone: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
  if (!match) throw new Error("Fecha y hora inválidas");
  const [, y, m, d, hour, minute] = match;
  const desired = Date.UTC(+y, +m - 1, +d, +hour, +minute);
  const possibleOffsets = new Set<number>();

  // Sampling both sides of the requested wall time captures every offset that
  // can participate in a nearby daylight-saving transition without assuming
  // a particular region or offset size.
  for (let minutes = -36 * 60; minutes <= 36 * 60; minutes += 30) {
    const sampledInstant = desired + minutes * 60_000;
    const parts = partsInZone(new Date(sampledInstant), timeZone);
    const represented = Date.UTC(
      +parts.year, +parts.month - 1, +parts.day, +parts.hour, +parts.minute, +parts.second
    );
    possibleOffsets.add(represented - sampledInstant);
  }

  const matchingInstants = new Set<number>();
  possibleOffsets.forEach((offset) => {
    const candidate = desired - offset;
    const parts = partsInZone(new Date(candidate), timeZone);
    if (`${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}` === value) {
      matchingInstants.add(candidate);
    }
  });

  if (matchingInstants.size === 0) {
    throw new Error("La hora seleccionada no existe en la zona horaria del espacio.");
  }
  if (matchingInstants.size > 1) {
    throw new Error(
      "La hora seleccionada es ambigua por un cambio de horario en la zona del espacio. Elige otra hora."
    );
  }
  return new Date([...matchingInstants][0]).toISOString();
}

export function isoToLocalInput(value: string, timeZone: string): string {
  const parts = partsInZone(new Date(value), timeZone);
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

export function formatTaskDate(value: string, timeZone: string): string {
  return new Intl.DateTimeFormat("es-PE", {
    timeZone, dateStyle: "medium", timeStyle: "short"
  }).format(new Date(value));
}
