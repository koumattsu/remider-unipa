// frontend/src/api/auth.ts

import apiClient from './client';

export const authApi = {
  getCurrentUser: async () => (await apiClient.get('/auth/me')).data,

  ensureGuestSession: async () => {
    // ✅ guest試行のSSOTは Login.tsx（df_guest_issued_v1）に寄せる
    //    二重ロックは「永久にguestを試さない」事故の原因になる
    return (await apiClient.post('/auth/guest')).data;
  },
};