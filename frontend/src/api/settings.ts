// frontend/src/api/settings.ts

import apiClient from './client';
import { NotificationSetting, NotificationSettingUpdate } from '../types';

export const settingsApi = {
  getNotification: async (): Promise<NotificationSetting> => {
    const response = await apiClient.get('/api/v1/settings/notification');
    return response.data;
  },

  updateNotification: async (setting: NotificationSettingUpdate): Promise<NotificationSetting> => {
    const response = await apiClient.post('/api/v1/settings/notification', setting);
    return response.data;
  },
};
