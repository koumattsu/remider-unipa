// frontend/src/api/auth.ts

import apiClient from './client';

export const authApi = {
  getCurrentUser: async () => (await apiClient.get('/auth/me')).data,

  ensureGuestSession: async () => {
    // ✅ guest試行のSSOTは Login.tsx（df_guest_issued_v1）に寄せる。
    //    ここで二重ロックすると「失敗後に永久に guest を試さない」事故が起きる。
    return (await apiClient.post('/auth/guest')).data;
  },
};