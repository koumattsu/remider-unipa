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
  timeout: 60000,
  withCredentials: true,
});

apiClient.interceptors.request.use(
  (config) => {
    const headers = (config.headers ?? {}) as any;
    config.headers = headers;
    return config;
  },
  (error) => Promise.reject(error),
);

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    return Promise.reject(error);
  },
);

export default apiClient;
