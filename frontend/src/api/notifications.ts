import apiClient from './client';

export type InAppNotification = {
  id: number;
  kind: string;
  title: string;
  body: string;
  deep_link: string;
  task_id: number | null;
  deadline_at_send: string;
  offset_hours: number;
  created_at: string;
};

export async function fetchInAppNotifications(limit = 30): Promise<InAppNotification[]> {
  const res = await apiClient.get('/api/v1/notifications/in-app', {
    params: { limit },
  });
  return res.data.items ?? [];
}

export async function dismissInAppNotification(id: number): Promise<void> {
  await apiClient.post(`/api/v1/notifications/in-app/${id}/dismiss`);
}
