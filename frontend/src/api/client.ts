import axios, { AxiosError } from 'axios';

const baseURL ='http://127.0.0.1:8000';
  //import.meta.env.VITE_API_BASE_URL ||
  //(import.meta.env.DEV
  //  ? 'http://127.0.0.1:8000'                       // ← 開発中はローカル backend
  //  : 'https://unipa-reminder-backend.onrender.com' // ← ビルド時は本番
  //'http://127.0.0.1:8000' );

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
