import { describe, expect, it } from "vitest";

import { resolveApiBaseUrl } from "./env";


describe("resolveApiBaseUrl", () => {
  it("uses and normalizes a deployment-provided URL", () => {
    expect(resolveApiBaseUrl(" https://api.example.com/api/v1/ ", "https://app.example.com"))
      .toBe("https://api.example.com/api/v1");
  });

  it("uses the application origin when no deployment URL is provided", () => {
    expect(resolveApiBaseUrl(undefined, "https://app.example.com"))
      .toBe("https://app.example.com/api/v1");
  });
});
