import type { V2TaskRecurrence } from "../types/v2Task";

function parseDate(value: string): Date { return new Date(`${value}T00:00:00Z`); }
function iso(date: Date): string { return date.toISOString().slice(0, 10); }
function daysInMonth(year: number, month: number): number { return new Date(Date.UTC(year, month + 1, 0)).getUTCDate(); }

export function recurrenceOccurrenceCount(recurrence: V2TaskRecurrence): number {
  if (!recurrence.date_from || !recurrence.date_until || recurrence.date_from > recurrence.date_until) return 0;
  const dates = new Set<string>();
  const start = parseDate(recurrence.date_from);
  const end = parseDate(recurrence.date_until);
  if (recurrence.pattern === "DAILY" || recurrence.pattern === "WEEKLY") {
    if (recurrence.pattern === "WEEKLY" && (recurrence.weekdays?.some((day) => !Number.isInteger(day) || day < 0 || day > 6) ?? true)) return 0;
    const weekdays = new Set(recurrence.weekdays ?? []);
    for (const current = new Date(start); current <= end; current.setUTCDate(current.getUTCDate() + 1)) {
      const mondayZero = (current.getUTCDay() + 6) % 7;
      if (recurrence.pattern === "DAILY" || weekdays.has(mondayZero)) dates.add(iso(current));
    }
  } else {
    const anchors = recurrence.month_days ?? [];
    if (anchors.length === 0 || anchors.some((anchor) => !Number.isInteger(anchor) || anchor < 1 || anchor > 31)) return 0;
    for (let year = start.getUTCFullYear(), month = start.getUTCMonth(); year < end.getUTCFullYear() || (year === end.getUTCFullYear() && month <= end.getUTCMonth());) {
      const last = daysInMonth(year, month);
      for (const anchor of anchors) {
        const candidate = new Date(Date.UTC(year, month, Math.min(anchor, last)));
        if (candidate >= start && candidate <= end) dates.add(iso(candidate));
      }
      month += 1; if (month === 12) { month = 0; year += 1; }
    }
  }
  return dates.size;
}
