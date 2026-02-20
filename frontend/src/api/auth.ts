// frontend/src/api/auth.ts

import apiClient from './client';

export const authApi = {
  getCurrentUser: async () => {
    const response = await apiClient.get('/auth/me');
    return response.data;
  },

  // ✅ 追加：ゲストセッション発行（LINE不要）
  ensureGuestSession: async () => {
    // サーバ側で cookie を set するだけでOK（戻り値は任意）
    const response = await apiClient.post('/auth/guest');
    return response.data;
  },
};