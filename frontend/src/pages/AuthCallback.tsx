// frontend/src/pages/AuthCallback.tsx

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const AUTH_TOKEN_KEY = 'auth_token';

export const AuthCallback = () => {
  const [message, setMessage] = useState('Processing...');
  const navigate = useNavigate();

  useEffect(() => {
    // ✅ SSOT: 認証は cookie session のみ。token は保存しない。
    try {
      localStorage.removeItem(AUTH_TOKEN_KEY);
    } catch {}

    setMessage('OK! Redirecting...');
    navigate('/dashboard', { replace: true });
  }, [navigate]);

  return <div style={{ padding: '2rem' }}>{message}</div>;
};