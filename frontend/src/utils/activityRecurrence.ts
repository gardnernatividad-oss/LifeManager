import type { ActivityRecurrencePattern } from "../types/v2Activity";

const parseDate = (value: string) => new Date(`${value}T00:00:00Z`);
const formatDate = (value: Date) => value.toISOString().slice(0, 10);

export function activityRecurrenceDates(input: { pattern: ActivityRecurrencePattern; dateFrom: string; dateUntil: string; weekdays?: number[]; monthDays?: number[] }): string[] {
  if (!input.dateFrom || !input.dateUntil || input.dateFrom > input.dateUntil) return [];
  const from = parseDate(input.dateFrom); const until = parseDate(input.dateUntil); const result = new Set<string>();
  if (input.pattern === "DAILY" || input.pattern === "WEEKLY") {
    for (const cursor = new Date(from); cursor <= until; cursor.setUTCDate(cursor.getUTCDate() + 1)) {
      const weekday = (cursor.getUTCDay() + 6) % 7;
      if (input.pattern === "DAILY" || input.weekdays?.includes(weekday)) result.add(formatDate(cursor));
    }
  } else {
    const cursor = new Date(Date.UTC(from.getUTCFullYear(), from.getUTCMonth(), 1));
    while (cursor <= until) {
      const last = new Date(Date.UTC(cursor.getUTCFullYear(), cursor.getUTCMonth() + 1, 0)).getUTCDate();
      for (const day of input.monthDays ?? []) {
        const candidate = new Date(Date.UTC(cursor.getUTCFullYear(), cursor.getUTCMonth(), Math.min(day, last)));
        if (candidate >= from && candidate <= until) result.add(formatDate(candidate));
      }
      cursor.setUTCMonth(cursor.getUTCMonth() + 1);
    }
  }
  return [...result].sort();
}
