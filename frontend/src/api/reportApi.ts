import { listTasks } from "./taskApi";
import type { ReportTaskCounts } from "../types/report";
import type { TaskListParams, TaskOutcome, TaskStatus } from "../types/task";

function filters(
  scheduledFrom: string,
  scheduledTo: string,
  outcome: TaskOutcome | "" = "",
  status: TaskStatus | "" = ""
): TaskListParams {
  return {
    page: 1,
    pageSize: 1,
    search: "",
    status,
    outcome,
    categoryId: "",
    projectId: "",
    scheduledFrom,
    scheduledTo,
    orderBy: "scheduled_at",
    orderDirection: "asc"
  };
}

export async function getReportTaskCounts(
  workspaceId: string,
  scheduledFrom: string,
  scheduledTo: string
): Promise<ReportTaskCounts> {
  const [all, completed, notCompleted, cancelled, pending, scheduled] = await Promise.all([
    listTasks(workspaceId, filters(scheduledFrom, scheduledTo)),
    listTasks(workspaceId, filters(scheduledFrom, scheduledTo, "completed")),
    listTasks(workspaceId, filters(scheduledFrom, scheduledTo, "not_completed")),
    listTasks(workspaceId, filters(scheduledFrom, scheduledTo, "cancelled")),
    listTasks(workspaceId, filters(scheduledFrom, scheduledTo, "", "pending")),
    listTasks(workspaceId, filters(scheduledFrom, scheduledTo, "", "scheduled"))
  ]);
  return {
    total: all.total,
    completed: completed.total,
    notCompleted: notCompleted.total,
    cancelled: cancelled.total,
    // Pending and scheduled are the backend's two mutually exclusive states
    // for Tasks whose terminal outcome is still null.
    unresolved: pending.total + scheduled.total
  };
}
