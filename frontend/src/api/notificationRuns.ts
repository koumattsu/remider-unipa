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
    };
  };
  run_counters: {
    inapp_created: number | null;
    webpush_sent: number | null;
    webpush_failed: number | null;
    webpush_deactivated: number | null;
  };
};

export async function fetchLatestNotificationRun(): Promise<NotificationRun> {
  const res = await apiClient.get('/admin/notification-runs/latest');
  return res.data;
}

export async function fetchRunSummary(runId: number): Promise<RunSummary> {
  const res = await apiClient.get(`/admin/notification-runs/${runId}/summary`);
  return res.data;
}
