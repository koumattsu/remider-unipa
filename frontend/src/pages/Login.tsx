// frontend/src/pages/Login.tsx

import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/auth';

const detectInAppBrowser = (): boolean => {
  try {
    const ua = navigator.userAgent || '';

    // X / Twitter in-app browser（iOS/Androidでそこそこ当たる）
    // 例: "Twitter for iPhone", "TwitterAndroid"
    if (/Twitter|TwitterAndroid/i.test(ua)) return true;

    // ついでに主要な in-app も雑に拾う（誤検知しても害は少ない：ログイン案内が出るだけ）
    // Instagram, Facebook, LINEなど
    if (/FBAN|FBAV|Instagram|Line\/|LINE/i.test(ua)) return true;

    return false;
  } catch {
    return false;
  }
};

export const Login: React.FC = () => {
  console.log('VITE_API_BASE_URL:', import.meta.env.VITE_API_BASE_URL);
  const navigate = useNavigate();

  const isInApp = useMemo(() => detectInAppBrowser(), []);
  const [isLoading, setIsLoading] = useState(true);
  const [showInAppGate, setShowInAppGate] = useState(false);

  useEffect(() => {
    (async () => {
      // ✅ まず in-app の可能性が高いなら、先に「Safari/Chromeで開く」導線を出す
      // ただし、すでにセッションがある場合はそのまま通してOK
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

      // ✅ 通常ブラウザは今まで通り
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

  const startGoogleLogin = () => {
    const rawBase =
      import.meta.env.VITE_API_BASE_URL ||
      (import.meta.env.DEV
        ? 'http://127.0.0.1:8000'
        : 'https://unipa-reminder-backend.onrender.com');

    const base = String(rawBase).replace(/\/+$/, '');

    const url = base.endsWith('/api/v1')
      ? `${base}/auth/google/authorize`
      : `${base}/api/v1/auth/google/authorize`;

    window.location.href = url;
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

  // ✅ in-appブラウザ検知時：最初から回避導線を出す（ループ防止）
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

  // ✅ 通常のログイン画面
  return (
    <div style={{ padding: '2rem', maxWidth: '600px', margin: '0 auto' }}>
      <h1 style={{ textAlign: 'center' }}>DueFlow</h1>
      <div style={{ marginTop: '2rem', padding: '2rem', border: '1px solid #ddd', borderRadius: '8px' }}>
        <h2>ログイン</h2>

        <p style={{ color: '#666', marginBottom: '1.0rem' }}>
          ログイン方法を選択してください
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

        <button
          onClick={startGoogleLogin}
          style={{
            width: '100%',
            padding: '1rem',
            fontSize: '1.1rem',
            backgroundColor: '#111',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            marginTop: '0.75rem',
          }}
        >
          Googleでログイン
        </button>

        {/* ✅ 念のための注記（通常ブラウザにも有益） */}
        <p style={{ color: '#777', marginTop: '1rem', fontSize: '0.9rem', lineHeight: 1.5 }}>
          ※ Xアプリ内ブラウザ / シークレットではログインが完了しない場合があります。
          その場合は Safari/Chrome で開いてください。
        </p>
      </div>
    </div>
  );
};