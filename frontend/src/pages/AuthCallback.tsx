// frontend/src/pages/AuthCallback.tsx

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const AUTH_TOKEN_KEY = 'auth_token';

export const AuthCallback = () => {
  const [message, setMessage] = useState('Processing...');
  const navigate = useNavigate();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');

    if (!token) {
      setMessage('Missing token');
      return;
    }

    // ✅ cookieが死んでも成立するための本線：Bearer token を保存
    localStorage.setItem(AUTH_TOKEN_KEY, token);

    setMessage('OK! token saved. Redirecting...');
    navigate('/dashboard', { replace: true });
  }, [navigate]);

  return <div style={{ padding: '2rem' }}>{message}</div>;
};