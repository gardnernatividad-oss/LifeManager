import axios from "axios";

import { getAccessToken, handleUnauthorized } from "../services/authToken";
import { env } from "../utils/env";

export const apiClient = axios.create({
  baseURL: env.apiBaseUrl,
  headers: {
    Accept: "application/json",
    "Content-Type": "application/json"
  }
});

apiClient.interceptors.request.use((config) => {
  const accessToken = getAccessToken();

  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }

  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      await handleUnauthorized();
    }

    return Promise.reject(error);
  }
);
