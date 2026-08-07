import type { ReportPeriod, ReportPeriodBounds } from "../types/report";
import { localDateTimeToIso } from "./taskDateTime";

function localDate(date: Date, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function shiftDate(value: string, days: number): string {
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day + days));
  return date.toISOString().slice(0, 10);
}

function monthStart(value: string): string {
  return `${value.slice(0, 7)}-01`;
}

function mondayStart(value: string): string {
  const [year, month, day] = value.split("-").map(Number);
  const weekday = new Date(Date.UTC(year, month - 1, day)).getUTCDay();
  return shiftDate(value, -(weekday === 0 ? 6 : weekday - 1));
}

export function getReportPeriodBounds(
  period: ReportPeriod,
  timeZone: string,
  customFrom = "",
  customTo = "",
  now = new Date()
): ReportPeriodBounds | null {
  const today = localDate(now, timeZone);
  let fromDate: string;
  let toDate: string;

  if (period === "custom") {
    if (!customFrom || !customTo || customFrom > customTo) return null;
    fromDate = customFrom;
    toDate = customTo;
  } else if (period === "this_week") {
    fromDate = mondayStart(today);
    toDate = shiftDate(fromDate, 6);
  } else if (period === "this_month") {
    fromDate = monthStart(today);
    const [year, month] = fromDate.split("-").map(Number);
    toDate = new Date(Date.UTC(year, month, 0)).toISOString().slice(0, 10);
  } else {
    fromDate = shiftDate(today, -29);
    toDate = today;
  }

  const scheduledFrom = localDateTimeToIso(`${fromDate}T00:00`, timeZone);
  const exclusiveEnd = localDateTimeToIso(`${shiftDate(toDate, 1)}T00:00`, timeZone);
  const scheduledTo = new Date(new Date(exclusiveEnd).getTime() - 1).toISOString();
  return { scheduledFrom, scheduledTo, fromDate, toDate };
}
