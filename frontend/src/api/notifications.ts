import { api } from "./client";
import type { AppNotification } from "./types";

export const notificationsApi = {
  list: (unreadOnly = false) =>
    api.get<AppNotification[]>("/notifications", { query: { unread_only: unreadOnly, limit: 100 } }),
  unreadCount: () => api.get<{ count: number }>("/notifications/unread-count"),
  markRead: (id: number) => api.post<AppNotification>(`/notifications/${id}/read`),
};
