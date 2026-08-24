import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  CSRF_COOKIE_NAME,
  configureSessionTransport,
  handleUnauthorized,
  readCsrfToken
} from "./sessionTransport";

describe("sessionTransport", () => {
  beforeEach(() => {
    document.cookie = `${CSRF_COOKIE_NAME}=; Max-Age=0; Path=/`;
    configureSessionTransport({});
  });

  it("reads only the public CSRF cookie", () => {
    document.cookie = `${CSRF_COOKIE_NAME}=csrf-value; Path=/`;
    expect(readCsrfToken()).toBe("csrf-value");
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
  });

  it("delegates 401 session loss to the in-memory handler", async () => {
    const handler = vi.fn();
    configureSessionTransport({ onUnauthorized: handler });
    await handleUnauthorized();
    expect(handler).toHaveBeenCalledOnce();
  });
});
