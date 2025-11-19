import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    // ダミー認証用ヘッダー（開発時）
    'X-Dummy-User-Id': '1',
  },
});

export default apiClient;

