// frontend/src/pages/AuthCallback.tsx

import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/auth';

const AUTH_TOKEN_KEY = 'auth_token';
const OAUTH_RETURN_KEY = 'df_oauth_returned_v1';
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const isRetryableAuthWarmupError = (error: unknown): boolean => {
  const e = error as any;
  const status = e?.response?.status;
  if (status === 401) return false; // 本当に未認証
  if (status === 400) return false; // 契約違反系
  // timeout / network / cold start っぽいものは再試行
  const code = String(e?.code ?? '');
  if (code === 'ECONNABORTED' || code === 'ERR_NETWORK') return true;
  // response が無い = backend起動待ち / network失敗 の可能性が高い
  if (!e?.response) return true;
  // 502/503/504 は起動中の可能性あり
  if ([502, 503, 504].includes(Number(status))) return true;
  return false;
};

const waitForAuthenticatedSession = async (
  onProgress: (message: string) => void
) => {
  const scheduleMs = [0, 1200, 2200, 3500, 5000, 7000];

  for (let i = 0; i < scheduleMs.length; i += 1) {
    if (scheduleMs[i] > 0) {
      onProgress(`DueFlowを起動しています...（${i + 1}/${scheduleMs.length}）`);
      await sleep(scheduleMs[i]);
    } else {
      onProgress('Checking session...');
    }

    try {
      return await authApi.getCurrentUser();
    } catch (error) {
      const lastAttempt = i === scheduleMs.length - 1;
      if (lastAttempt || !isRetryableAuthWarmupError(error)) {
        throw error;
      }
    }
  }
  throw new Error('session warmup failed');
};

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
    let cancelled = false;

    (async () => {
      try {
        localStorage.removeItem(AUTH_TOKEN_KEY);
      } catch {}

      try {
        sessionStorage.setItem(OAUTH_RETURN_KEY, String(Date.now()));
      } catch {}

      try {
        await waitForAuthenticatedSession((nextMessage) => {
          if (!cancelled) setMessage(nextMessage);
        });

        try {
          sessionStorage.removeItem(OAUTH_RETURN_KEY);
        } catch {}

        if (!cancelled) {
          setMessage('OK! Redirecting...');
          navigate('/dashboard', { replace: true });
        }
        return;
      } catch (e) {
        try {
          sessionStorage.removeItem(OAUTH_RETURN_KEY);
        } catch {}

        if (cancelled) return;

        setFailed(true);
        setMessage('ログインを完了できませんでした');
        setDetail(
          '無料プラン環境では、初回アクセス時にサーバー起動待ちが発生することがあります。\n' +
            '少し待ってから再度お試しください。\n\n' +
            'また、Xアプリ内ブラウザやシークレットモードでは、ログイン用Cookieが保存されず、ログインが完了しないことがあります。\n' +
            '「Safari/Chromeで開く」で再度お試しください。'
        );
      }
    })();

    return () => {
      cancelled = true;
    };
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
          無料プラン環境では、初回アクセス時にサーバー起動待ちが発生することがあります。
          その場合は数秒〜数十秒ほどかかることがあります。
        </div>
      </div>
    );
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
          <li>少し待ってから再度試す</li>
          <li>Xアプリの「…」→「Safariで開く / ブラウザで開く」を選ぶ</li>
          <li>それが無い場合は、上の「URLをコピー」→ Safari/Chrome に貼り付けて開く</li>
          <li>シークレットモードはOFF推奨</li>
        </ul>
      </div>
    </div>
  );
};