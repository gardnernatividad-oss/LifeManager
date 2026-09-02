import { apiClient } from "./client";
import type { NotificationPreferences, PushSubscriptionPayload, PushSubscriptionRecord } from "../types/v2Notifications";
import { env } from "../utils/env";

const v2 = (path: string) => new URL(`/api/v2${path}`, env.apiBaseUrl).toString();

export const getNotificationPreferences = async () => (await apiClient.get<NotificationPreferences>(v2("/notification-preferences"))).data;
export const updateNotificationPreferences = async (payload: NotificationPreferences) => (await apiClient.put<NotificationPreferences>(v2("/notification-preferences"), payload)).data;
export const registerPushSubscription = async (payload: PushSubscriptionPayload) => (await apiClient.post<PushSubscriptionRecord>(v2("/push-subscriptions"), payload)).data;
export const unregisterPushSubscription = async (id: string) => { await apiClient.delete(v2(`/push-subscriptions/${id}`)); };
