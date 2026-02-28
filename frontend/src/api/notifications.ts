// frontend/src/api/notifications.ts
import apiClient from './client';

export type InAppNotification = {
  id: number;
  run_id?: number | null;
  kind: string;
  title: string;
  body: string;
  body_ui?: string; // ✅ UI表示用（括弧内を除去した本文）
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

// ✅ UI表示用：本文の括弧内を非表示にする（監査用のbodyは残す）
const simplifyNotifBodyForUi = (s: string) => {
  if (!s) return s;
  return s
    .split('\n')
    .map((line) =>
      line
        .replace(/\s*\([^)]*\)\s*/g, ' ')
        .replace(/\s{2,}/g, ' ')
        .trim()
    )
    .join('\n')
    .trim();
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
  const items = (res.data.items ?? []) as InAppNotification[];
  return items.map((n) => ({
    ...n,
    body_ui: simplifyNotifBodyForUi(n.body),
  }));
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
