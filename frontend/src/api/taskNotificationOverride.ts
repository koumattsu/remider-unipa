// frontend/src/api/taskNotificationOverride.ts
import apiClient from './client';

export type TaskNotificationOverridePayload = {
  enable_morning: boolean | null;
  reminder_offsets_hours: number[] | null;
};

export const taskNotificationOverrideApi = {
  get: async (taskId: number) => {
    const res = await apiClient.get(
      `/api/v1/tasks/${taskId}/notification-override`
    );
    return res.data;
  },

  upsert: async (taskId: number, payload: TaskNotificationOverridePayload) => {
    const res = await apiClient.put(
      `/api/v1/tasks/${taskId}/notification-override`,
      payload
    );
    return res.data;
  },
};
