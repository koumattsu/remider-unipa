// frontend/src/api/client.ts

import axios, { AxiosError } from 'axios';

const rawBase =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV
    ? 'http://127.0.0.1:8000'
    : 'https://unipa-reminder-backend.onrender.com');

// ✅ 末尾の / を落としてから /api/v1 を付与（壊れにくい）
const baseURL = `${String(rawBase).replace(/\/+$/, '')}/api/v1`;

const apiClient = axios.create({
  baseURL,
  timeout: 15000, // ✅ 体感優先（必要なら個別APIで上書き）
  withCredentials: true,
});

// ✅ 任意：APIデバッグ（本番でも env でON/OFFできる）
const API_DEBUG = String(import.meta.env.VITE_API_DEBUG ?? '') === '1';

apiClient.interceptors.request.use(
  (config) => {
    const headers = (config.headers ?? {}) as any;
    config.headers = headers;

    // ✅ SSOT: 認証は cookie session のみ（Authorization は付与しない）

    if (API_DEBUG) {
      const method = String(config.method ?? 'GET').toUpperCase();
      const url = `${config.baseURL ?? ''}${config.url ?? ''}`;
      console.log('[api:req]', method, url, { params: config.params });
    }
    return config;
  },
  (error) => Promise.reject(error),
);

apiClient.interceptors.response.use(
  (response) => {
    if (API_DEBUG) {
      const method = String(response.config.method ?? 'GET').toUpperCase();
      const url = `${response.config.baseURL ?? ''}${response.config.url ?? ''}`;
      console.log('[api:res]', method, url, response.status);
    }
    return response;
  },
  (error: AxiosError) => {
    if (API_DEBUG) {
      const cfg = (error.config ?? undefined) as
        | { method?: unknown; url?: unknown; baseURL?: unknown }
        | undefined;

      const method = String(cfg?.method ?? 'GET').toUpperCase();
      const url = `${String(cfg?.baseURL ?? '')}${String(cfg?.url ?? '')}`;

      console.log('[api:err]', method, url, error.response?.status ?? 'NO_STATUS');
    }
    return Promise.reject(error);
  },
);

export default apiClient;