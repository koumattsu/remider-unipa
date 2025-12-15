// frontend/src/api/weeklyTasks.ts

import apiClient from './client';
import { WeeklyTask, WeeklyTaskCreate, WeeklyTaskUpdate } from '../types';

export const weeklyTasksApi = {
  getAll: async (): Promise<WeeklyTask[]> => {
    const res = await apiClient.get('/api/v1/weekly-tasks/');
    return res.data;
  },

  create: async (payload: WeeklyTaskCreate): Promise<WeeklyTask> => {
    const res = await apiClient.post('/api/v1/weekly-tasks/', payload);
    return res.data;
  },

  update: async (id: number, payload: WeeklyTaskUpdate): Promise<WeeklyTask> => {
    const res = await apiClient.patch(`/api/v1/weekly-tasks/${id}`, payload);
    return res.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/api/v1/weekly-tasks/${id}`);
  },

  materialize: async (): Promise<{ created: number; skipped: number }> => {
    const res = await apiClient.post('/api/v1/weekly-tasks/materialize');
    return res.data;
  },
};
