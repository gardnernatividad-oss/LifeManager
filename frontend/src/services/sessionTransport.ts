type UnauthorizedHandler = () => void | Promise<void>;

export const CSRF_COOKIE_NAME = "lifemanager_v2_csrf";
export const CSRF_HEADER_NAME = "X-CSRF-Token";

let unauthorizedHandler: UnauthorizedHandler | undefined;

export function readCsrfToken(): string | null {
  const prefix = `${CSRF_COOKIE_NAME}=`;
  const match = document.cookie
    .split(";")
    .map((value) => value.trim())
    .find((value) => value.startsWith(prefix));
  return match ? decodeURIComponent(match.slice(prefix.length)) : null;
}

export function configureSessionTransport(options: {
  onUnauthorized?: UnauthorizedHandler;
}) {
  unauthorizedHandler = options.onUnauthorized;
}

export async function handleUnauthorized() {
  await unauthorizedHandler?.();
}
