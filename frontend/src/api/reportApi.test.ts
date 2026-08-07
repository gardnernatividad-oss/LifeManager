import { beforeEach, describe, expect, it, vi } from "vitest";

import { listTasks } from "./taskApi";
import { getReportTaskCounts } from "./reportApi";

vi.mock("./taskApi", () => ({ listTasks: vi.fn() }));

describe("getReportTaskCounts", () => {
  beforeEach(() => vi.clearAllMocks());

  it("uses pagination totals from one-row requests without fetching full datasets", async () => {
    vi.mocked(listTasks)
      .mockResolvedValueOnce({ items: [], total: 12, page: 1, page_size: 1, total_pages: 12 })
      .mockResolvedValueOnce({ items: [], total: 7, page: 1, page_size: 1, total_pages: 7 })
      .mockResolvedValueOnce({ items: [], total: 2, page: 1, page_size: 1, total_pages: 2 })
      .mockResolvedValueOnce({ items: [], total: 1, page: 1, page_size: 1, total_pages: 1 })
      .mockResolvedValueOnce({ items: [], total: 1, page: 1, page_size: 1, total_pages: 1 })
      .mockResolvedValueOnce({ items: [], total: 1, page: 1, page_size: 1, total_pages: 1 });

    await expect(getReportTaskCounts("workspace", "from", "to")).resolves.toEqual({
      total: 12,
      completed: 7,
      notCompleted: 2,
      cancelled: 1,
      unresolved: 2
    });
    expect(listTasks).toHaveBeenCalledTimes(6);
    expect(vi.mocked(listTasks).mock.calls.every(([, params]) => params.page === 1 && params.pageSize === 1)).toBe(true);
    expect(vi.mocked(listTasks).mock.calls.map(([, params]) => params.outcome)).toEqual(["", "completed", "not_completed", "cancelled", "", ""]);
    expect(vi.mocked(listTasks).mock.calls.map(([, params]) => params.status)).toEqual(["", "", "", "", "pending", "scheduled"]);
    expect(vi.mocked(listTasks).mock.calls.every(([, params]) => params.scheduledFrom === "from" && params.scheduledTo === "to")).toBe(true);
  });
});
