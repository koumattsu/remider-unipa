// frontend/src/api/taskNotificationOverride.ts
import apiClient from './client';

export type TaskNotificationOverridePayload = {
  enable_morning: boolean | null;
  reminder_offsets_hours: number[] | null;
};

export const taskNotificationOverrideApi = {
  getAll: async () => {
    const res = await apiClient.get('/tasks/notification-overrides'); // ✅ 末尾 / を削除
    return res.data as Array<{
      task_id: number;
      enable_morning: boolean | null;
      reminder_offsets_hours: number[] | null;
    }>;
  },

  get: async (taskId: number) => {
    const res = await apiClient.get(`/tasks/${taskId}/notification-override`); // ✅ 末尾 / を削除
    return res.data;
  },

  upsert: async (taskId: number, payload: TaskNotificationOverridePayload) => {
    const res = await apiClient.put(`/tasks/${taskId}/notification-override`, payload); // ✅ 末尾 / を削除
    return res.data;
  },
};
