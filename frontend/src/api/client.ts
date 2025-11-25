import axios, { AxiosError } from 'axios';

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

const apiClient = axios.create({
  baseURL,
  timeout: 10000, // 10秒タイムアウト
});

// =============
// リクエスト前処理
// =============
apiClient.interceptors.request.use(
  (config) => {
    // ダミーユーザー（あとでLINEログインに変更できる）
    // 型エラーを避けるため headers を any として扱う
    const headers = (config.headers ?? {}) as any;

    headers['X-Dummy-User-Id'] = '1';
    config.headers = headers;

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);


// =============
// レスポンスエラー処理
// =============
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response) {
      console.error('API Error:', {
        status: error.response.status,
        data: error.response.data,
        url: error.config?.url,
      });
    } else if (error.request) {
      console.error('No response received:', error.message);
    } else {
      console.error('Request setup error:', error.message);
    }

    return Promise.reject(error);
  }
);

export default apiClient;
