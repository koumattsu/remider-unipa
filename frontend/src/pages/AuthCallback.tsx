// frontend/src/pages/AuthCallback.tsx

import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/auth';

const AUTH_TOKEN_KEY = 'auth_token';
const OAUTH_RETURN_KEY = 'df_oauth_returned_v1';

export const AuthCallback = () => {
  const [message, setMessage] = useState('Processing...');
  const [failed, setFailed] = useState(false);
  const [detail, setDetail] = useState('');
  const navigate = useNavigate();

  const currentUrl = useMemo(() => {
    try {
      return window.location.href;
    } catch {
      return '';
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        localStorage.removeItem(AUTH_TOKEN_KEY);
      } catch {}

      // ✅ Dashboard側が「OAuth直後」を判定できるように印を付ける
      try {
        sessionStorage.setItem(OAUTH_RETURN_KEY, String(Date.now()));
      } catch {}

      setMessage('Checking session...');

      try {
        // ✅ Cookieが本当に付いたか確認
        await authApi.getCurrentUser();
        // ✅ 成功したら「OAuth直後フラグ」を消す（次回の誤判定防止）
        try {
          sessionStorage.removeItem(OAUTH_RETURN_KEY);
        } catch {}

        setMessage('OK! Redirecting...');
        navigate('/dashboard', { replace: true });
        return;
      } catch (e) {
        // ✅ 失敗したらフラグは残さない（誤判定の芽を潰す）
        try {
          sessionStorage.removeItem(OAUTH_RETURN_KEY);
        } catch {}
        setFailed(true);
        setMessage('ログインを完了できませんでした');
        setDetail(
          'Xアプリ内ブラウザやシークレットモードでは、ログイン用Cookieが保存されず、ログインが完了しないことがあります。\n' +
            '「Safari/Chromeで開く」で再度お試しください。'
        );
      }
    })();
  }, [navigate]);

  const copyUrl = async () => {
    try {
      await navigator.clipboard.writeText(currentUrl);
      alert('URLをコピーしました。Safari/Chromeで貼り付けて開いてください。');
    } catch {
      alert('コピーに失敗しました。URLを長押ししてコピーしてください。');
    }
  };

  if (!failed) {
    return <div style={{ padding: '2rem' }}>{message}</div>;
  }

  return (
    <div style={{ padding: '2rem', maxWidth: 720, margin: '0 auto' }}>
      <h2 style={{ marginBottom: '0.75rem' }}>{message}</h2>

      <div
        style={{
          whiteSpace: 'pre-line',
          color: '#444',
          lineHeight: 1.6,
          border: '1px solid rgba(0,0,0,.12)',
          borderRadius: 12,
          padding: '1rem',
          background: 'rgba(0,0,0,.03)',
        }}
      >
        {detail}
      </div>

      <div style={{ marginTop: '1rem' }}>
        <button
          onClick={() => {
            try {
              sessionStorage.removeItem(OAUTH_RETURN_KEY);
            } catch {}
            navigate('/login', { replace: true });
          }}
          style={{
            width: '100%',
            padding: '0.9rem',
            fontSize: '1rem',
            backgroundColor: '#111',
            color: 'white',
            border: 'none',
            borderRadius: 8,
            cursor: 'pointer',
          }}
        >
          ログイン画面に戻る
        </button>

        <button
          onClick={copyUrl}
          style={{
            width: '100%',
            padding: '0.9rem',
            fontSize: '1rem',
            backgroundColor: '#fff',
            color: '#111',
            border: '1px solid rgba(0,0,0,.2)',
            borderRadius: 8,
            cursor: 'pointer',
            marginTop: '0.75rem',
          }}
        >
          今のURLをコピー（Safari/Chromeで開く用）
        </button>
      </div>

      <div style={{ marginTop: '1rem', color: '#666', fontSize: 14, lineHeight: 1.6 }}>
        <div>📌 対処:</div>
        <ul>
          <li>Xアプリの「…」→「Safariで開く / ブラウザで開く」を選ぶ</li>
          <li>それが無い場合は、上の「URLをコピー」→ Safari/Chrome に貼り付けて開く</li>
          <li>シークレットモードはOFF推奨</li>
        </ul>
      </div>
    </div>
  );
};