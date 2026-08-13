import { beforeEach, describe, expect, it, vi } from "vitest";

import { getAuthenticatedUser, login } from "./authApi";
import { apiClient } from "./client";
import { testUser } from "../test/testUser";

vi.mock("./client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn()
  }
}));

describe("authApi V1 paths", () => {
  beforeEach(() => vi.clearAllMocks());

  it("uses only the versioned login endpoint", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      data: { access_token: "token", token_type: "bearer" }
    });
    await login({ email: "ada@example.com", password: "secret" });
    expect(apiClient.post).toHaveBeenCalledWith("http://localhost:8000/api/v1/auth/login", {
      email: "ada@example.com",
      password: "secret"
    });
  });

  it("uses only the versioned current-user endpoint", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: testUser });
    await getAuthenticatedUser();
    expect(apiClient.get).toHaveBeenCalledWith("http://localhost:8000/api/v1/auth/me");
  });
});
