// frontend/src/api/weeklyTasks.ts

import apiClient from './client';
import {
  WeeklyTask,
  WeeklyTaskCreate,
  WeeklyTaskUpdate,
} from '../types';

export const weeklyTasksApi = {
  // 一覧取得
  getAll: async (): Promise<WeeklyTask[]> => {
    const res = await apiClient.get('/api/v1/weekly-tasks/');
    return res.data;
  },

  // 新規作成
  create: async (payload: WeeklyTaskCreate): Promise<WeeklyTask> => {
    const res = await apiClient.post('/api/v1/weekly-tasks/', payload);
    return res.data;
  },

  // 更新
  update: async (
    id: number,
    payload: WeeklyTaskUpdate
  ): Promise<WeeklyTask> => {
    const res = await apiClient.patch(`/api/v1/weekly-tasks/${id}`, payload);
    return res.data;
  },

  // 削除
  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/api/v1/weekly-tasks/${id}`);
  },
};
