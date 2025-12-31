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

export type ActionEffectivenessSnapshotItem = {
  id: number;
  bucket: Bucket;
  computed_at: string; // ISO
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

export type ActionEffectivenessSnapshotsResponse = {
  items: ActionEffectivenessSnapshotItem[];
};

export const analyticsActionsApi = {
  recordApplied: async (params: {
    action_id: string;
    bucket: Bucket;
    applied_at?: string; // ISO
    payload?: Record<string, any>;
  }): Promise<{ ok: boolean; event: ActionAppliedEvent }> => {
    const { action_id, bucket, applied_at, payload } = params;

    const body = {
      applied_at: applied_at ?? null,
      payload: payload ?? {},
    };

    const res = await apiClient.post('/analytics/actions/applied', body, {
      params: { action_id, bucket },
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

  getEffectivenessByFeature: async (params?: {
    version?: string; // default v1
    from?: string;
    to?: string;
    window_days?: number;
    min_total?: number;
    limit_events?: number;
    limit_samples_per_event?: number;
  }): Promise<ActionEffectivenessByFeatureResponse> => {
    const res = await apiClient.get('/analytics/actions/effectiveness/by-feature', { params });
    return res.data;
  },

  // ✅ Priority 8-C②: snapshots は「再計算せず」履歴資産を読むだけ
  getEffectivenessSnapshots: async (params?: {
    bucket?: Bucket;
    limit?: number;
  }): Promise<ActionEffectivenessSnapshotsResponse> => {
    const res = await apiClient.get('/analytics/actions/effectiveness/snapshots', { params });
    return res.data;
  },
};

export type ActionEffectivenessByFeatureItem = {
  action_id: string;
  feature_key: string;
  feature_value: string;
  total_events: number;
  improved_events: number;
  improved_rate: number; // 0-1
};

export type ActionEffectivenessByFeatureResponse = {
  range: {
    timezone: string;
    version: string;
    from?: string | null;
    to?: string | null;
    window_days: number;
    min_total: number;
    limit_events: number;
    limit_samples_per_event: number;
  };
  items: ActionEffectivenessByFeatureItem[];
};