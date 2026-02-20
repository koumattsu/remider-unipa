// frontend/src/pages/Login.tsx

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/auth';

export const Login: React.FC = () => {
  console.log('VITE_API_BASE_URL:', import.meta.env.VITE_API_BASE_URL);
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(true);
  const [guestLoading, setGuestLoading] = useState(false);

  useEffect(() => {
    checkAuth();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const checkAuth = async () => {
    try {
      await authApi.getCurrentUser();
      navigate('/dashboard');
      return;
    } catch {
      // ✅ 未ログインなら「ログイン画面」を出す（勝手にguest発行しない）
      setIsLoading(false);
    }
  };

  const startGuest = async () => {
    setGuestLoading(true);
    try {
      await authApi.ensureGuestSession();
      await authApi.getCurrentUser();
      navigate('/dashboard');
    } catch (e) {
      // 失敗したらログイン画面に戻す
      setGuestLoading(false);
      alert('ゲスト開始に失敗しました。もう一度お試しください。');
    }
  };

  const startLineLogin = () => {
    const rawBase =
      import.meta.env.VITE_API_BASE_URL ||
      (import.meta.env.DEV
        ? 'http://127.0.0.1:8000'
        : 'https://unipa-reminder-backend.onrender.com');

    const base = String(rawBase).replace(/\/+$/, '');

    const url = base.endsWith('/api/v1')
      ? `${base}/auth/line/authorize`
      : `${base}/api/v1/auth/line/authorize`;

    window.location.href = url;
  };

  if (isLoading) {
    return <div style={{ padding: '2rem', textAlign: 'center' }}>読み込み中...</div>;
  }

  return (
    <div style={{ padding: '2rem', maxWidth: '600px', margin: '0 auto' }}>
      <h1 style={{ textAlign: 'center' }}>UniPA Reminder App</h1>

      <div style={{ marginTop: '2rem', padding: '2rem', border: '1px solid #ddd', borderRadius: '8px' }}>
        <h2>ログイン</h2>

        <button
          onClick={startGuest}
          disabled={guestLoading}
          style={{
            width: '100%',
            padding: '1rem',
            fontSize: '1.1rem',
            backgroundColor: '#111',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: guestLoading ? 'not-allowed' : 'pointer',
            opacity: guestLoading ? 0.7 : 1,
            marginBottom: '1rem',
          }}
        >
          {guestLoading ? 'ゲスト開始中...' : 'ゲストで開始（無料）'}
        </button>

        <p style={{ color: '#666', marginBottom: '1.0rem' }}>
          LINEログインは後からでもOK（将来の有料機能向け）
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