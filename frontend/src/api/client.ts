// frontend/src/api/client.ts
import axios from 'axios';

const baseURL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';

const apiClient = axios.create({
  baseURL,
});

// 今はダミーユーザーで運用するので、共通ヘッダーで付ける
apiClient.interceptors.request.use((config) => {
  config.headers = config.headers ?? {};
  (config.headers as any)['X-Dummy-User-Id'] = '1';
  return config;
});

export default apiClient;
