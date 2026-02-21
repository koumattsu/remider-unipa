// frontend/src/api/auth.ts
import apiClient from './client';

export const authApi = {
  getCurrentUser: async () => (await apiClient.get('/auth/me')).data,

  logout: async () => {
    // backendは /api/v1/auth/logout (GET/POST両方ある)
    // Cookie消すだけなら GET で十分
    const res = await apiClient.get('/auth/logout');
    localStorage.removeItem('auth_token');
    return res.data;
  },
};