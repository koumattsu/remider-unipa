// frontend/src/api/notificationRuns.ts
import apiClient from './client';

export type NotificationRun = {
  id: number;
  status: string;
  error_summary?: string | null;
  users_processed?: number | null;
  due_candidates_total?: number | null;
  morning_candidates_total?: number | null;
  inapp_created?: number | null;
  webpush_sent?: number | null;
  webpush_failed?: number | null;
  webpush_deactivated?: number | null;
  line_sent?: number | null;
  line_failed?: number | null;
  started_at?: string | null;
  finished_at?: string | null;
  stats?: any;
};

export type RunSummary = {
  run: {
    id: number;
    status: string;
    started_at: string | null;
    finished_at: string | null;
    stats?: any;
  };
  inapp: {
    total: number;
    dismissed_count?: number;
    dismiss_rate?: number;
    webpush: {
      delivered: number;
      failed: number;
      deactivated: number;
      unknown: number;
      events?: {
        sent: number;
        failed: number;
        deactivated: number;
        skipped: number;
        unknown: number;
      };
      // ✅ message軸（開封率）
      sent_messages?: number;
      opened_messages?: number;
      open_rate?: number; // 0..100 想定（backendで丸め）
    };
  };
  run_counters: {
    inapp_created: number | null;
    webpush_sent: number | null;
    webpush_failed: number | null;
    webpush_deactivated: number | null;
  };
};

const isOptionalNotFound = (e: any) => {
  const s = e?.response?.status;
  return s === 404 || s === 401 || s === 403;
};

export async function fetchLatestNotificationRun(): Promise<NotificationRun | null> {
  // 1) まずは admin ルート（存在するならそれを使う）
  try {
    const res = await apiClient.get('/admin/notification-runs/latest');
    return res.data;
  } catch (e: any) {
    // admin が無い/権限が無い → optional扱いで次の候補へ
    if (!isOptionalNotFound(e)) throw e;
  }

  // 2) fallback（もし public ルートがある構成でも壊れない）
  try {
    const res = await apiClient.get('/notification-runs/latest');
    return res.data;
  } catch (e: any) {
    // ここも optional（監査はなくてもStatsは動く）
    if (isOptionalNotFound(e)) return null;
    throw e;
  }
}

export async function fetchRunSummary(runId: number): Promise<RunSummary> {
  const res = await apiClient.get(`/admin/notification-runs/${runId}/summary`);
  return res.data;
}
