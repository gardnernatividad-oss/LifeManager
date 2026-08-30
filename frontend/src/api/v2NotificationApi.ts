import { apiClient } from "./client";
import type { NotificationPreferences, PushSubscriptionPayload, PushSubscriptionRecord } from "../types/v2Notifications";

export const getNotificationPreferences = async () => (await apiClient.get<NotificationPreferences>("/api/v2/notification-preferences")).data;
export const updateNotificationPreferences = async (payload: NotificationPreferences) => (await apiClient.put<NotificationPreferences>("/api/v2/notification-preferences", payload)).data;
export const registerPushSubscription = async (payload: PushSubscriptionPayload) => (await apiClient.post<PushSubscriptionRecord>("/api/v2/push-subscriptions", payload)).data;
export const unregisterPushSubscription = async (id: string) => { await apiClient.delete(`/api/v2/push-subscriptions/${id}`); };
