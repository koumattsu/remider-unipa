// frontend/src/api/client.ts

import axios, { AxiosError } from 'axios';

const baseURL =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV
    ? 'http://127.0.0.1:8000'
    : 'https://unipa-reminder-backend.onrender.com');

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
  (error: AxiosError) => {
    // 略（今のままでOK）
    return Promise.reject(error);
  },
);

export default apiClient;
