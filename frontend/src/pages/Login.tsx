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
      <div className="df-auth-page">
        <div className="df-auth-wrap">
          <div className="glass glass-strong glass-card df-auth-card df-auth-card--compact">
            <h1 className="df-auth-brand df-title">DueFlow</h1>
            <div className="df-auth-loading">
              {warmupMessage || '読み込み中...'}
            </div>
          </div>
        </div>
      </div>
    );
  }
  
  if (showInAppGate) {
    return (
      <div className="df-auth-page">
        <div className="df-auth-wrap df-auth-wrap--wide">
          <div className="glass glass-strong glass-card df-auth-card">
            <h1 className="df-auth-brand df-title">DueFlow</h1>
            <h2 className="df-auth-heading">
              Xアプリ内ブラウザではログインできないことがあります
            </h2>
  
            <div className="df-auth-note df-auth-note--warning">
              {`この画面は「Xアプリ内ブラウザ」で開かれている可能性があります。
  この環境ではログイン用Cookieが保存されず、ログインが完了しないことがあります。
  
  ✅ 対処：
  1) Xアプリの「…」→「Safariで開く / ブラウザで開く」
  2) それが無ければ「URLをコピー」→ Safari/Chrome に貼り付けて開く
  3) シークレットモードはOFF推奨`}
            </div>
  
            <button
              onClick={copyUrl}
              className="df-btn df-btn--secondary"
            >
              URLをコピー（Safari/Chromeで開く）
            </button>
  
            <button
              onClick={() => setShowInAppGate(false)}
              className="df-btn df-btn--dark"
            >
              （理解した上で）このままログインを試す
            </button>
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div className="df-auth-page">
      <div className="df-auth-wrap">
        <h1 className="df-auth-brand df-title">DueFlow</h1>
  
        <div className="glass glass-strong glass-card df-auth-card">
          <h2 className="df-auth-heading">ログイン</h2>
  
          <p className="df-auth-subtext">
            ログイン方法を選択してください
          </p>
  
          <div
            className={
              backendReady
                ? 'df-auth-status df-auth-status--ready'
                : 'df-auth-status df-auth-status--warming'
            }
          >
            <div className="df-auth-status-title">
              {backendReady ? 'DueFlowは起動済みです' : 'DueFlowを先に起動しています'}
            </div>
            <div className="df-auth-status-text">
              {warmupMessage || 'サーバー起動待ちを減らすため、事前準備しています。'}
            </div>
          </div>
  
          <button
            onClick={() => startOAuthLogin('line')}
            disabled={loginStarting !== null}
            className="df-btn df-btn--line"
          >
            {loginStarting === 'line' ? 'LINEログインを開始しています...' : 'LINEでログイン'}
          </button>
  
          <button
            onClick={() => startOAuthLogin('google')}
            disabled={loginStarting !== null}
            className="df-btn df-btn--google"
          >
            {loginStarting === 'google'
              ? 'Googleログインを開始しています...'
              : 'Googleでログイン'}
          </button>
  
          <p className="df-auth-help">
            ※ Xアプリ内ブラウザ / シークレットではログインが完了しない場合があります。
            その場合は Safari / Chrome で開いてください。
          </p>
  
          {(prewarming || !backendReady) && (
            <p className="df-auth-help df-auth-help--sub">
              ※ Render無料プランでは、初回ログイン時に数秒〜数十秒の起動待ちが発生することがあります。
            </p>
          )}
        </div>
      </div>
    </div>
  );
};