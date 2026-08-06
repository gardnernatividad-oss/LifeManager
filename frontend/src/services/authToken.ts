type AccessTokenProvider = () => string | null;
type UnauthorizedHandler = () => void | Promise<void>;

export const ACCESS_TOKEN_STORAGE_KEY = "lifemanager.accessToken";

export function readAccessToken(): string | null {
  return window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY);
}

export function storeAccessToken(token: string): void {
  window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, token);
}

export function removeAccessToken(): void {
  window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
}

let accessTokenProvider: AccessTokenProvider = readAccessToken;
let unauthorizedHandler: UnauthorizedHandler | undefined;

export function configureAuthTransport(options: {
  getAccessToken: AccessTokenProvider;
  onUnauthorized?: UnauthorizedHandler;
}) {
  accessTokenProvider = options.getAccessToken;
  unauthorizedHandler = options.onUnauthorized;
}

export function getAccessToken() {
  return accessTokenProvider();
}

export async function handleUnauthorized() {
  await unauthorizedHandler?.();
}
