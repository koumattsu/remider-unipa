// frontend/src/pages/Login.tsx

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/auth';

export const Login: React.FC = () => {
  console.log('VITE_API_BASE_URL:', import.meta.env.VITE_API_BASE_URL);
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // ダミー認証なので自動的にログイン済みとして扱う
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      await authApi.getCurrentUser();
      // 認証済みならダッシュボードへ
      navigate('/dashboard');
    } catch (error) {
      // 未ログイン(401)は想定内。ログイン画面を表示するだけ
      setIsLoading(false);
    }
  };

  const startLineLogin = () => {
    const base = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');
    if (!base) {
      alert('VITE_API_BASE_URL が未設定です');
      return;
    }
    window.location.href = `${base}/api/v1/auth/line/authorize`;
  };

  if (isLoading) {
    return <div style={{ padding: '2rem', textAlign: 'center' }}>読み込み中...</div>;
  }

  return (
    <div style={{ padding: '2rem', maxWidth: '600px', margin: '0 auto' }}>
      <h1 style={{ textAlign: 'center' }}>UniPA Reminder App</h1>
      <div style={{ marginTop: '2rem', padding: '2rem', border: '1px solid #ddd', borderRadius: '8px' }}>
        <h2>ログイン</h2>
        <p style={{ color: '#666', marginBottom: '1.5rem' }}>
          LINEアカウントでログインしてください。
        </p>
        <button
          onClick={startLineLogin}
          style={{
            width: '100%',
            padding: '1rem',
            fontSize: '1.1rem',
            backgroundColor: '#00C300',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
        >
          LINEでログイン
        </button>
      </div>
    </div>
  );
};

