// frontend/src/api/client.ts
import axios, { AxiosError } from 'axios';

const rawBase =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV
    ? 'http://127.0.0.1:8000'
    : 'https://unipa-reminder-backend.onrender.com');

const normalized = String(rawBase).replace(/\/+$/, '');

// ✅ rawBase に /api/v1 が入ってても入ってなくても、最終的に1回だけになる
const baseURL = `${String(rawBase).replace(/\/+$/, '')}/api/v1`;

const apiClient = axios.create({
  baseURL,
  timeout: 30000,
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
  (error: AxiosError) => Promise.reject(error),
);

export default apiClient;
