export function resolveApiBaseUrl(
  configuredUrl: string | undefined,
  origin: string
): string {
  const configured = configuredUrl?.trim();
  if (configured) return configured.replace(/\/$/, "");
  return `${origin}/api/v1`;
}

export const env = {
  apiBaseUrl: resolveApiBaseUrl(
    import.meta.env.VITE_API_BASE_URL,
    window.location.origin
  )
} as const;
