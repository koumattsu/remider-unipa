// frontend/src/pages/AuthCallback.tsx

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const AUTH_TOKEN_KEY = 'auth_token';

const getTokenFromUrl = (): string | null => {
  // 1) 通常の ?token=...
  const p1 = new URLSearchParams(window.location.search);
  const t1 = p1.get('token');
  if (t1) return t1;

  // 2) HashRouter: /#/auth-callback?token=... は hash 側に入る
  const hash = window.location.hash || '';
  const qIndex = hash.indexOf('?');
  if (qIndex >= 0) {
    const query = hash.slice(qIndex + 1);
    const p2 = new URLSearchParams(query);
    const t2 = p2.get('token');
    if (t2) return t2;
  }

  return null;
};

export const AuthCallback = () => {
  const [message, setMessage] = useState('Processing...');
  const navigate = useNavigate();

  useEffect(() => {
    const token = getTokenFromUrl();

    if (!token) {
      setMessage('Missing token');
      return;
    }

    localStorage.setItem(AUTH_TOKEN_KEY, token);

    setMessage('OK! token saved. Redirecting...');
    navigate('/dashboard', { replace: true });
  }, [navigate]);

  return <div style={{ padding: '2rem' }}>{message}</div>;
};