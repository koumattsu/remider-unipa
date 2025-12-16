// frontend/src/api/taskNotificationOverride.ts
import apiClient from './client';

export type TaskNotificationOverridePayload = {
  enable_morning: boolean | null;
  reminder_offsets_hours: number[] | null;
};

export const taskNotificationOverrideApi = {
  getAll: async () => {
    const res = await apiClient.get('/api/v1/tasks/notification-overrides/');
    return res.data as Array<{
      task_id: number;
      enable_morning: boolean | null;
      reminder_offsets_hours: number[] | null;
    }>;
  },
  
  get: async (taskId: number) => {
    const res = await apiClient.get(
      `/api/v1/tasks/${taskId}/notification-override/`
    );
    return res.data;
  },

  upsert: async (taskId: number, payload: TaskNotificationOverridePayload) => {
    const res = await apiClient.put(
      `/api/v1/tasks/${taskId}/notification-override/`,
      payload
    );
    return res.data;
  },
};
