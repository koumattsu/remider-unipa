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

export type InAppSummary = {
  total: number;
  dismissed: number;
  dismiss_rate: number; // 0-100
};


export type InAppNotificationsSummary = {
  range: { from: string | null; to: string | null };
  // ✅ UIの「通知反応」はここ（Web Pushのみ）に寄せる
  // total = webpush sent, dismissed = webpush opened, dismiss_rate = open_rate
  total: number;
  dismissed: number;
  dismiss_rate: number; // 0-100

  // ✅ InAppNotification は資産として保持（UI分母には使わない）
  inapp?: InAppSummary;

  webpush_events: {
    sent: number;
    opened?: number;
    failed: number;
    deactivated: number;
    skipped: number;
    unknown: number;
  };
};

export async function fetchInAppNotifications(
  limit = 30,
  opts?: { includeDismissed?: boolean; from?: string; to?: string }
): Promise<InAppNotification[]> {
  const res = await apiClient.get('/notifications/in-app', {
    params: {
      limit,
      include_dismissed: opts?.includeDismissed ?? false,
      from: opts?.from,
      to: opts?.to,
    },
  });
  return res.data.items ?? [];
}

export async function fetchInAppNotificationsSummary(opts?: { from?: string; to?: string }): Promise<InAppNotificationsSummary> {
  const res = await apiClient.get('/notifications/in-app/summary', {
    params: {
      from: opts?.from,
      to: opts?.to,
    },
  });
  return res.data;
}

export async function dismissInAppNotification(id: number): Promise<void> {
  await apiClient.post(`/notifications/in-app/${id}/dismiss`);
}
