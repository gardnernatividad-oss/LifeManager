type AccessTokenProvider = () => string | null;
type UnauthorizedHandler = () => void | Promise<void>;

let accessTokenProvider: AccessTokenProvider = () => null;
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
