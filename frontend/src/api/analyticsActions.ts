// frontend/src/api/analyticsActions.ts
import apiClient from './client';

export type Bucket = 'week' | 'month';

export type ActionAppliedEvent = {
  id: number;
  action_id: string;
  bucket: Bucket;
  applied_at: string;
  payload: Record<string, any>;
  created_at: string;
};

export type ActionEffectivenessItem = {
  action_id: string;
  applied_count: number;
  measured_count: number;
  improved_count: number;
  improved_rate: number; // 0-1
  avg_delta_missed_rate: number; // -1..1 (missed_rate_after - before)
};

export type ActionEffectivenessResponse = {
  range: {
    timezone: string;
    from?: string | null;
    to?: string | null;
    window_days: number;
    min_total: number;
    limit_events: number;
  };
  items: ActionEffectivenessItem[];
};

export const analyticsActionsApi = {
  recordApplied: async (params: {
    action_id: string;
    bucket: Bucket;
    applied_at?: string; // ISO
    payload?: Record<string, any>;
  }): Promise<{ ok: boolean; event: ActionAppliedEvent }> => {
    // backend が action_id を引数で受けてるので params に載せる
    const res = await apiClient.post('/analytics/actions/applied', null, {
      params,
    });
    return res.data;
  },

  listApplied: async (params?: {
    action_id?: string;
    bucket?: Bucket;
    limit?: number;
  }): Promise<{ items: ActionAppliedEvent[] }> => {
    const res = await apiClient.get('/analytics/actions/applied', { params });
    return res.data;
  },

  getEffectiveness: async (params?: {
    from?: string;
    to?: string;
    window_days?: number;
    min_total?: number;
    limit_events?: number;
  }): Promise<ActionEffectivenessResponse> => {
    const res = await apiClient.get('/analytics/actions/effectiveness', { params });
    return res.data;
  },
};
