// frontend/src/api/notifications.ts
import apiClient from './client';

export type InAppNotification = {
  id: number;
  run_id?: number | null;
  kind: string;
  title: string;
  body: string;
  deep_link: string;
  task_id: number | null;
  deadline_at_send: string;
  offset_hours: number;
  created_at: string;
  dismissed_at?: string | null;
  extra?: any; // JSONB（webpush観測を最小で使う）
};

export async function fetchInAppNotifications(
  limit = 30,
  opts?: { includeDismissed?: boolean }
): Promise<InAppNotification[]> {
  const res = await apiClient.get('/notifications/in-app', {
    params: { limit, include_dismissed: opts?.includeDismissed ?? false },
  });
  return res.data.items ?? [];
}

export async function dismissInAppNotification(id: number): Promise<void> {
  await apiClient.post(`/notifications/in-app/${id}/dismiss`);
}
