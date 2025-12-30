// frontend/src/api/analyticsOutcomes.ts
import apiClient from './client';

export type Bucket = 'week' | 'month';

export type OutcomesRange = {
  bucket: Bucket;
  from?: string | null;
  to?: string | null;
};

export type OutcomesSummaryItem = {
  total: number;
  done: number;
  missed: number;
  done_rate: number; // backendが 0-1 でも 0-100 でも一旦受ける（表示側で防御する）
};

export type OutcomesSummaryResponse = {
  range: OutcomesRange;
  items: OutcomesSummaryItem[];
};

export type OutcomesByCourseRow = {
  // backendの返しが course_name / course_hash / course_key どれでも壊れないようにする
  course_name?: string | null;
  course_hash?: string | null;
  course_key?: string | null;

  total: number;
  missed: number;
  missed_rate: number;
};

export type OutcomesByCourseResponse = {
  range: OutcomesRange;
  items: OutcomesByCourseRow[];
};

export const analyticsOutcomesApi = {
  async getSummary(params: { bucket: Bucket; from?: string; to?: string }): Promise<OutcomesSummaryResponse> {
    const res = await apiClient.get<OutcomesSummaryResponse>('/analytics/outcomes/summary', { params });
    return res.data;
  },

  async getByCourse(params: { bucket: Bucket; from?: string; to?: string }): Promise<OutcomesByCourseResponse> {
    const res = await apiClient.get<OutcomesByCourseResponse>('/analytics/outcomes/by-course', { params });
    return res.data;
  },

  // ✅ 追加：feature別 missed率
  async getMissedByFeature(params: {
    version?: string;
    from?: string;
    to?: string;
    limit?: number;
  }): Promise<OutcomesByFeatureResponse> {
    const res = await apiClient.get<OutcomesByFeatureResponse>(
      '/analytics/outcomes/missed-by-feature',
      { params },
    );
    return res.data;
  },
  // ✅ 追加：course × feature の missed率（Priority 3-C）
  async getCourseXFeature(params: {
    version?: string;
    from?: string;
    to?: string;
    limit?: number;
    course_hash?: string;
  }): Promise<OutcomesCourseXFeatureResponse> {
    const res = await apiClient.get<OutcomesCourseXFeatureResponse>(
      '/analytics/outcomes/course-x-feature',
      { params },
    );
    return res.data;
  },
};

export type OutcomesByFeatureRow = {
  feature_key: string;
  feature_value: string | number | boolean | null;
  total: number;
  missed: number;
  missed_rate: number; // 0-1 or 0-100 は表示側で防御
};

export type OutcomesByFeatureResponse = {
  range: OutcomesRange & { version?: string | null; limit?: number | null };
  items: OutcomesByFeatureRow[];
};

export type OutcomesCourseXFeatureRow = {
  course_hash: string;
  feature_key: string;
  feature_value: string; // backendが string 化して返す仕様（壊れにくい）
  total: number;
  missed: number;
  missed_rate: number; // 0-1 or 0-100 は表示側で防御
};

export type OutcomesCourseXFeatureResponse = {
  range: OutcomesRange & { version?: string | null; limit?: number | null; course_hash?: string | null };
  items: OutcomesCourseXFeatureRow[];
};
