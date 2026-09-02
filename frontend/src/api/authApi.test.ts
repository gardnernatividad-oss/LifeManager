import { beforeEach, describe, expect, it, vi } from "vitest";

import { changePassword, getAuthenticatedUser, getProfile, listTimezones, login, logout, registerUser, updateAuthenticatedUser } from "./authApi";
import { apiClient } from "./client";
import { testUser } from "../test/testUser";

vi.mock("./client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn() }
}));

describe("V2 cookie auth API", () => {
  beforeEach(() => vi.clearAllMocks());

  it("logs in without expecting an access token", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: testUser });
    await expect(login({ email: "ada@example.com", password: "secret" })).resolves.toEqual(testUser);
    expect(apiClient.post).toHaveBeenCalledWith(
      "http://localhost:3000/api/v2/auth/login",
      { email: "ada@example.com", password: "secret" }
    );
  });

  it("restores and closes the cookie session through V2", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: testUser });
    await getAuthenticatedUser();
    await logout();
    expect(apiClient.get).toHaveBeenCalledWith("http://localhost:3000/api/v2/me");
    expect(apiClient.post).toHaveBeenCalledWith("http://localhost:3000/api/v2/auth/logout");
  });

  it("uses the restricted V2 registration request", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: { accepted: true } });
    const payload = { email: "ada@example.com", password: "ValidPassword!", first_name: "Ada", last_name: "Lovelace", turnstile_token: "ephemeral-response" };
    await registerUser(payload);
    expect(apiClient.post).toHaveBeenCalledWith(
      "http://localhost:3000/api/v2/auth/registration-requests",
      payload
    );
  });

  it("reads and updates Profile and timezone options only through V2", async () => {
    const profile = { id: testUser.id, email: testUser.email, first_name: "Ada", last_name: "Lovelace", timezone: "America/Lima", lock_version: 3 };
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: profile }).mockResolvedValueOnce({ data: { items: ["America/Lima", "UTC"] } });
    vi.mocked(apiClient.patch).mockResolvedValue({ data: { ...profile, first_name: "Augusta", lock_version: 4 } });

    await expect(getProfile()).resolves.toEqual(profile);
    await expect(listTimezones()).resolves.toEqual(["America/Lima", "UTC"]);
    const payload = { first_name: "Augusta", last_name: "Lovelace", timezone: "America/Lima", lock_version: 3 };
    await updateAuthenticatedUser(payload);

    expect(apiClient.get).toHaveBeenNthCalledWith(1, "http://localhost:3000/api/v2/configuration/profile");
    expect(apiClient.get).toHaveBeenNthCalledWith(2, "http://localhost:3000/api/v2/configuration/timezones");
    expect(apiClient.patch).toHaveBeenCalledWith("http://localhost:3000/api/v2/configuration/profile", payload);
    expect(JSON.stringify([
      vi.mocked(apiClient.get).mock.calls,
      vi.mocked(apiClient.patch).mock.calls,
    ])).not.toContain("/api/v1");
  });

  it("changes only the authenticated password through the dedicated V2 contract", async () => {
    const payload = { current_password: "CurrentPassword!", new_password: "NewPassword!" };
    await changePassword(payload);
    expect(apiClient.post).toHaveBeenCalledWith(
      "http://localhost:3000/api/v2/configuration/password",
      payload,
    );
    expect(JSON.stringify(vi.mocked(apiClient.post).mock.calls)).not.toContain("/api/v1");
  });
});
