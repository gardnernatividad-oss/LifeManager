import { beforeEach, describe, expect, it, vi } from "vitest";

import { getAuthenticatedUser, listTimezones, login, registerUser, updateAuthenticatedUser } from "./authApi";
import { apiClient } from "./client";
import { testUser } from "../test/testUser";

vi.mock("./client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn()
  }
}));

describe("authApi V1 paths", () => {
  beforeEach(() => vi.clearAllMocks());

  it("uses only the versioned login endpoint", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      data: { access_token: "token", token_type: "bearer" }
    });
    await login({ email: "ada@example.com", password: "secret" });
    expect(apiClient.post).toHaveBeenCalledWith("http://localhost:3000/api/v1/auth/login", {
      email: "ada@example.com",
      password: "secret"
    });
  });

  it("registers with the exact final V1 payload", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: testUser });
    const payload = { email: "ada@example.com", password: "secret", first_name: "Ada", last_name: "Lovelace" };
    await registerUser(payload);
    expect(apiClient.post).toHaveBeenCalledWith("http://localhost:3000/api/v1/auth/register", payload);
    expect(payload).not.toHaveProperty("username");
    expect(payload).not.toHaveProperty("timezone");
    expect(payload).not.toHaveProperty("workspace");
  });

  it("updates only the profile through the current-user endpoint", async () => {
    vi.mocked(apiClient.patch).mockResolvedValue({ data: testUser });
    const payload = { first_name: "Augusta", last_name: "King", timezone: "Europe/London" };
    await updateAuthenticatedUser(payload);
    expect(apiClient.patch).toHaveBeenCalledWith("http://localhost:3000/api/v1/auth/me", payload);
    expect(payload).not.toHaveProperty("email");
  });

  it("loads the authoritative timezone catalog", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { items: ["America/Lima", "Europe/London"] } });
    await expect(listTimezones()).resolves.toEqual(["America/Lima", "Europe/London"]);
    expect(apiClient.get).toHaveBeenCalledWith("http://localhost:3000/api/v1/timezones");
  });

  it("uses only the versioned current-user endpoint", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: testUser });
    await getAuthenticatedUser();
    expect(apiClient.get).toHaveBeenCalledWith("http://localhost:3000/api/v1/auth/me");
  });
});
