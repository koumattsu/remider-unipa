// frontend/src/api/auth.ts
import apiClient from './client';

export const authApi = {
  getCurrentUser: async () => (await apiClient.get('/auth/me')).data,

  logout: async () => {
    // backendは /api/v1/auth/logout (GET/POST両方ある)
    // Cookie消すだけなら GET で十分
    return (await apiClient.get('/auth/logout')).data;
  },
};