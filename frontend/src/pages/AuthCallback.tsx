import { useEffect, useState } from 'react';

export const AuthCallback = () => {
  const [message, setMessage] = useState('Processing...');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const state = params.get('state');

    const expectedState = sessionStorage.getItem('line_oauth_state');

    if (!code || !state) {
      setMessage('Missing code/state');
      return;
    }
    if (!expectedState || state !== expectedState) {
      setMessage('Invalid state');
      return;
    }

    setMessage(`OK! state verified. code=${code}`);
    // 次ステップでここから backend /auth/line/exchange を叩く
  }, []);

  return <div style={{ padding: '2rem' }}>{message}</div>;
};
