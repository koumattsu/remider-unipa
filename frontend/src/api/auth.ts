// frontend/src/api/auth.ts

import apiClient from './client';

export const authApi = {
  getCurrentUser: async () => (await apiClient.get('/auth/me')).data,

  ensureGuestSession: async () => {
    const key = 'df_guest_attempted_v1';
    if (typeof window !== 'undefined' && sessionStorage.getItem(key) === '1') {
      throw new Error('guest already attempted');
    }
    if (typeof window !== 'undefined') sessionStorage.setItem(key, '1');
    return (await apiClient.post('/auth/guest')).data;
  },
};