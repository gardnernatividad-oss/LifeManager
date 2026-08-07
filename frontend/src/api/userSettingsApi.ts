import { apiClient } from "./client";
import type { UserSettings, UserSettingsWrite } from "../types/settings";

export async function getUserSettings(): Promise<UserSettings> {
  return (await apiClient.get<UserSettings>("/users/me/settings")).data;
}

export async function updateUserSettings(payload: UserSettingsWrite): Promise<UserSettings> {
  return (await apiClient.put<UserSettings>("/users/me/settings", payload)).data;
}
