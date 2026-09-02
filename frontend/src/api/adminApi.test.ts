import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "./client";
import { disableAdminUser, listAdminUsers } from "./adminApi";

vi.mock("./client", () => ({ apiClient: { get: vi.fn(), post: vi.fn() } }));

describe("adminApi", () => {
  beforeEach(() => vi.clearAllMocks());

  it("uses paginated V2 users without a V1 fallback", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { items: [], total: 0, page: 1, page_size: 25, total_pages: 0 } });
    await listAdminUsers({ page: 1, page_size: 25, account_status: "ACTIVE", search: "Ada" });
    const url = String(vi.mocked(apiClient.get).mock.calls[0][0]);
    expect(url).toContain("/api/v2/admin/users?");
    expect(url).toContain("account_status=ACTIVE");
    expect(url).not.toContain("/api/v1");
  });

  it("sends only lock_version when disabling an account", async () => {
    const user = { id: "u1", email: "user@example.com", first_name: "User", last_name: "One", timezone: "America/Lima", account_status: "ACTIVE" as const, global_role: null, email_verified_at: "2026-01-01T00:00:00Z", status_changed_at: "2026-01-01T00:00:00Z", lock_version: 3, created_at: "2026-01-01T00:00:00Z" };
    vi.mocked(apiClient.post).mockResolvedValue({ data: user });
    await disableAdminUser(user);
    expect(apiClient.post).toHaveBeenCalledWith(expect.stringContaining("/api/v2/admin/users/u1/disable"), { lock_version: 3 });
  });
});
