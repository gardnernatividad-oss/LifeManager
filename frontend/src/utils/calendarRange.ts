import { localDateTimeToIso } from "./taskDateTime";

export type CalendarView = "DAY" | "WEEK";

export function localCalendarDate(value: Date, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(value);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

export function addCalendarDays(value: string, days: number): string {
  const date = new Date(`${value}T12:00:00Z`); date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function mondayOfWeek(value: string): string {
  const date = new Date(`${value}T12:00:00Z`); const mondayOffset = (date.getUTCDay() + 6) % 7;
  return addCalendarDays(value, -mondayOffset);
}

export function calendarRange(anchor: string, view: CalendarView, timeZone: string) {
  const first = view === "WEEK" ? mondayOfWeek(anchor) : anchor;
  const after = addCalendarDays(first, view === "WEEK" ? 7 : 1);
  return { first, after, from: localDateTimeToIso(`${first}T00:00`, timeZone), to: localDateTimeToIso(`${after}T00:00`, timeZone) };
}

export function activityLocalDate(value: string, timeZone: string): string {
  return localCalendarDate(new Date(value), timeZone);
}
