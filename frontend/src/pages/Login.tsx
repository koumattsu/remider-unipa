// frontend/src/pages/Login.tsx

import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/auth';

const detectInAppBrowser = (): boolean => {
  try {
    const ua = navigator.userAgent || '';

    if (/Twitter|TwitterAndroid/i.test(ua)) return true;
    if (/FBAN|FBAV|Instagram|Line\/|LINE/i.test(ua)) return true;

    return false;
  } catch {
    return false;
  }
};

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const getBackendBaseUrl = (): string => {
  const rawBase =
    import.meta.env.VITE_API_BASE_URL ||
    (import.meta.env.DEV
      ? 'http://127.0.0.1:8000'
      : 'https://unipa-reminder-backend.onrender.com');

  return String(rawBase).replace(/\/+$/, '');
};

const getAuthorizeUrl = (provider: 'google' | 'line'): string => {
  const base = getBackendBaseUrl();
  return base.endsWith('/api/v1')
    ? `${base}/auth/${provider}/authorize`
    : `${base}/api/v1/auth/${provider}/authorize`;
};

const getBuildUrl = (): string => {
  const base = getBackendBaseUrl();
  return base.endsWith('/api/v1')
    ? base.replace(/\/api\/v1$/, '/build')
    : `${base}/build`;
};

const isRetryableWarmupError = (error: unknown): boolean => {
  const e = error as any;
  const status = Number(e?.response?.status ?? 0);

  if (!e?.response) return true;
  if ([425, 429, 502, 503, 504].includes(status)) return true;

  return false;
};

const prewarmBackend = async (
  onProgress?: (message: string) => void
): Promise<boolean> => {
  const scheduleMs = [0, 1200, 2200, 3500, 5000];
  const buildUrl = getBuildUrl();

  for (let i = 0; i < scheduleMs.length; i += 1) {
    if (scheduleMs[i] > 0) {
      onProgress?.(`DueFlowを起動しています...（${i + 1}/${scheduleMs.length}）`);
      await sleep(scheduleMs[i]);
    } else {
      onProgress?.('DueFlowを起動しています...');
    }

    try {
      const res = await fetch(buildUrl, {
        method: 'GET',
        cache: 'no-store',
        credentials: 'omit',
      });
      if (res.ok) return true;
      if (![425, 429, 502, 503, 504].includes(res.status)) return false;
    } catch (error) {
      if (!isRetryableWarmupError(error)) return false;
    }
  }

  return false;
};

export const Login: React.FC = () => {
  const navigate = useNavigate();

  const isInApp = useMemo(() => detectInAppBrowser(), []);
  const [isLoading, setIsLoading] = useState(true);
  const [showInAppGate, setShowInAppGate] = useState(false);
  const [backendReady, setBackendReady] = useState(false);
  const [prewarming, setPrewarming] = useState(false);
  const [warmupMessage, setWarmupMessage] = useState('');
  const [loginStarting, setLoginStarting] = useState<'google' | 'line' | null>(null);
  const prewarmPromiseRef = useRef<Promise<boolean> | null>(null);

  const ensureBackendReady = async (): Promise<boolean> => {
    if (backendReady) return true;
    if (!prewarmPromiseRef.current) {
      setPrewarming(true);
      prewarmPromiseRef.current = prewarmBackend((message) => {
        setWarmupMessage(message);
      }).then((ok) => {
        setBackendReady(ok);
        setPrewarming(false);
        if (ok) {
          setWarmupMessage('DueFlowの準備ができました');
        } else {
          setWarmupMessage('サーバー起動待ちが発生する場合があります');
        }
        return ok;
      });
    }
    return prewarmPromiseRef.current;
  };

  useEffect(() => {
    (async () => {
      void ensureBackendReady();

      if (isInApp) {
        try {
          await authApi.getCurrentUser();
          navigate('/dashboard');
          return;
        } catch {
          setShowInAppGate(true);
          setIsLoading(false);
          return;
        }
      }

      try {
        await authApi.getCurrentUser();
        navigate('/dashboard');
        return;
      } catch {
        setIsLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const copyUrl = async () => {
    const url = (() => {
      try {
        return window.location.href;
      } catch {
        return '';
      }
    })();

    try {
      await navigator.clipboard.writeText(url);
      alert('URLをコピーしました。Safari/Chromeに貼り付けて開いてください。');
    } catch {
      alert('コピーに失敗しました。URLを長押ししてコピーしてください。');
    }
  };

  const startOAuthLogin = async (provider: 'google' | 'line') => {
    setLoginStarting(provider);
    setWarmupMessage('DueFlowを起動しています...');

    try {
      await ensureBackendReady();
    } finally {
      window.location.href = getAuthorizeUrl(provider);
    }
  };

  if (isLoading) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center' }}>
        {warmupMessage || '読み込み中...'}
      </div>
    );
  }

  if (showInAppGate) {
    return (
      <div style={{ padding: '2rem', maxWidth: 720, margin: '0 auto' }}>
        <h1 style={{ textAlign: 'center', marginBottom: '1rem' }}>DueFlow</h1>

        <h2 style={{ marginBottom: '0.75rem' }}>
          Xアプリ内ブラウザではログインできないことがあります
        </h2>

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
          {`この画面は「Xアプリ内ブラウザ」で開かれている可能性があります。
この環境ではログイン用Cookieが保存されず、ログインが完了しないことがあります。

✅ 対処：
1) Xアプリの「…」→「Safariで開く / ブラウザで開く」
2) それが無ければ「URLをコピー」→ Safari/Chrome に貼り付けて開く
3) シークレットモードはOFF推奨`}
        </div>

        <button
          onClick={copyUrl}
          style={{
            width: '100%',
            padding: '0.95rem',
            fontSize: '1rem',
            backgroundColor: '#fff',
            color: '#111',
            border: '1px solid rgba(0,0,0,.2)',
            borderRadius: 10,
            cursor: 'pointer',
            marginTop: '1rem',
          }}
        >
          URLをコピー（Safari/Chromeで開く）
        </button>

        <button
          onClick={() => setShowInAppGate(false)}
          style={{
            width: '100%',
            padding: '0.95rem',
            fontSize: '1rem',
            backgroundColor: '#111',
            color: 'white',
            border: 'none',
            borderRadius: 10,
            cursor: 'pointer',
            marginTop: '0.75rem',
          }}
        >
          （理解した上で）このままログインを試す
        </button>
      </div>
    );
  }

  return (
    <div style={{ padding: '2rem', maxWidth: '600px', margin: '0 auto' }}>
      <h1 style={{ textAlign: 'center' }}>DueFlow</h1>
      <div style={{ marginTop: '2rem', padding: '2rem', border: '1px solid #ddd', borderRadius: '8px' }}>
        <h2>ログイン</h2>

        <p style={{ color: '#666', marginBottom: '1rem' }}>
          ログイン方法を選択してください
        </p>

        <div
          style={{
            marginBottom: '1rem',
            padding: '0.85rem 1rem',
            border: '1px solid rgba(0,0,0,.12)',
            borderRadius: 12,
            background: backendReady ? 'rgba(0, 195, 0, 0.08)' : 'rgba(0,0,0,.03)',
            color: '#444',
            lineHeight: 1.5,
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: '0.25rem' }}>
            {backendReady ? 'DueFlowは起動済みです' : 'DueFlowを先に起動しています'}
          </div>
          <div style={{ fontSize: '0.92rem' }}>
            {warmupMessage || 'サーバー起動待ちを減らすため、事前準備しています。'}
          </div>
        </div>

        <button
          onClick={() => startOAuthLogin('line')}
          disabled={loginStarting !== null}
          style={{
            width: '100%',
            padding: '1rem',
            fontSize: '1.1rem',
            backgroundColor: '#00C300',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: loginStarting ? 'not-allowed' : 'pointer',
            opacity: loginStarting && loginStarting !== 'line' ? 0.7 : 1,
          }}
        >
          {loginStarting === 'line' ? 'LINEログインを開始しています...' : 'LINEでログイン'}
        </button>

        <button
          onClick={() => startOAuthLogin('google')}
          disabled={loginStarting !== null}
          style={{
            width: '100%',
            padding: '1rem',
            fontSize: '1.1rem',
            backgroundColor: '#111',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: loginStarting ? 'not-allowed' : 'pointer',
            marginTop: '0.75rem',
            opacity: loginStarting && loginStarting !== 'google' ? 0.7 : 1,
          }}
        >
          {loginStarting === 'google' ? 'Googleログインを開始しています...' : 'Googleでログイン'}
        </button>

        <p style={{ color: '#777', marginTop: '1rem', fontSize: '0.9rem', lineHeight: 1.5 }}>
          ※ Xアプリ内ブラウザ / シークレットではログインが完了しない場合があります。
          その場合は Safari/Chrome で開いてください。
        </p>

        {(prewarming || !backendReady) && (
          <p style={{ color: '#777', marginTop: '0.75rem', fontSize: '0.88rem', lineHeight: 1.5 }}>
            ※ Render無料プランでは、初回ログイン時に数秒〜数十秒の起動待ちが発生することがあります。
          </p>
        )}
      </div>
    </div>
  );
};