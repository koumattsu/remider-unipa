import axios, { AxiosError } from 'axios';

const baseURL =
  import.meta.env.VITE_API_BASE_URL ||
  'https://unipa-reminder-backend.onrender.com'; // ← ここも本番にしとく

const LINE_USER_ID =
  import.meta.env.VITE_LINE_USER_ID || 'Uf7ec7ba2180b713c38d377eec2d9dfcb';

const apiClient = axios.create({
  baseURL,
  timeout: 10000,
});

apiClient.interceptors.request.use(
  (config) => {
    const headers = (config.headers ?? {}) as any;

    // 今後はこれだけ使う
    headers['X-Line-User-Id'] = LINE_USER_ID;

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
