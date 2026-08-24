import { beforeEach, describe, expect, it, vi } from "vitest";

import { getAuthenticatedUser, login, logout, registerUser } from "./authApi";
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
    const payload = { email: "ada@example.com", password: "ValidPassword!", first_name: "Ada", last_name: "Lovelace" };
    await registerUser(payload);
    expect(apiClient.post).toHaveBeenCalledWith(
      "http://localhost:3000/api/v2/auth/registration-requests",
      payload
    );
  });
});
