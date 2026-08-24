import axios from "axios";

import {
  CSRF_HEADER_NAME,
  handleUnauthorized,
  readCsrfToken
} from "../services/sessionTransport";
import { env } from "../utils/env";

export const apiClient = axios.create({
  baseURL: env.apiBaseUrl,
  withCredentials: true,
  headers: {
    Accept: "application/json",
    "Content-Type": "application/json"
  }
});

apiClient.interceptors.request.use((config) => {
  const method = config.method?.toUpperCase() ?? "GET";
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrfToken = readCsrfToken();
    if (csrfToken) {
      config.headers[CSRF_HEADER_NAME] = csrfToken;
    }
  }

  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (
      axios.isAxiosError(error) &&
      error.response?.status === 401
    ) {
      await handleUnauthorized();
    }

    return Promise.reject(error);
  }
);
