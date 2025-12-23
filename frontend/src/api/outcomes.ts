// frontend/src/api/outcomes.ts
import apiClient from './client';

export type Outcome = 'done' | 'missed';

export type OutcomeLog = {
  task_id: number;
  deadline: string;       // ISO
  outcome: Outcome;
  evaluated_at: string;   // ISO
};

export const outcomesApi = {
  async list(params?: { from?: string; to?: string }): Promise<OutcomeLog[]> {
    const res = await apiClient.get<OutcomeLog[]>('/outcomes', { params });
    return res.data;
  },
};
