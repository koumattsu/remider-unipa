// frontend/src/components/SafariInstallBanner.tsx

import React, { useEffect, useMemo, useState } from 'react';

const HIDE_KEY = 'dueflow_hide_safari_install_banner_v1';

function detect() {
  const ua = navigator.userAgent || '';

  const isIOS = /iPhone|iPad|iPod/i.test(ua);
  const isIPadOS = navigator.platform === 'MacIntel' && (navigator as any).maxTouchPoints > 1;
  const ios = isIOS || isIPadOS;

  const isCriOS = /CriOS/i.test(ua);    // Chrome iOS
  const isFxiOS = /FxiOS/i.test(ua);    // Firefox iOS
  const isEdgiOS = /EdgiOS/i.test(ua);  // Edge iOS
  const isGSA = /GSA/i.test(ua);        // Google App iOS
  const isOPiOS = /OPiOS/i.test(ua);    // Opera iOS

  const isSafari = /Safari/i.test(ua) && !isCriOS && !isFxiOS && !isEdgiOS && !isGSA && !isOPiOS;

  const isStandalone =
    window.matchMedia?.('(display-mode: standalone)')?.matches ||
    (navigator as any).standalone === true;

  return { ios, isSafari, isStandalone };
}

export const SafariInstallBanner: React.FC = () => {
  const [dismissed, setDismissed] = useState(false);
  const { ios, isSafari, isStandalone } = useMemo(() => detect(), []);

  useEffect(() => {
    try {
      const hidden = window.localStorage.getItem(HIDE_KEY) === '1';
      setDismissed(hidden);
    } catch {
      // noop
    }
  }, []);

  const shouldShow = ios && !isStandalone && !isSafari && !dismissed;
  if (!shouldShow) return null;

  const close = () => {
    setDismissed(true);
    try {
      window.localStorage.setItem(HIDE_KEY, '1');
    } catch {
      // noop
    }
  };

  const copyUrl = async () => {
    const url = window.location.href;
    try {
      await navigator.clipboard.writeText(url);
      alert('URLをコピーしました。Safariで貼り付けて開いてください。');
    } catch {
      try {
        const el = document.createElement('textarea');
        el.value = url;
        el.style.position = 'fixed';
        el.style.top = '-1000px';
        document.body.appendChild(el);
        el.focus();
        el.select();
        document.execCommand('copy');
        document.body.removeChild(el);
        alert('URLをコピーしました。Safariで貼り付けて開いてください。');
      } catch {
        alert('URLのコピーに失敗しました。手動でSafariに貼り付けてください。');
      }
    }
  };

  return (
    <div
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 999,
        padding: '0.6rem 0.75rem',
        marginBottom: '0.75rem',
        borderRadius: 16,
        border: '1px solid rgba(255,255,255,.12)',
        background: 'rgba(255,255,255,.06)',
        backdropFilter: 'blur(14px)',
        WebkitBackdropFilter: 'blur(14px)',
        boxShadow: '0 14px 34px rgba(0,0,0,0.35)',
      }}
      role="region"
      aria-label="Safariで開く案内"
    >
      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 800, letterSpacing: '0.02em' }}>
            ホーム画面に追加するには Safari で開いてね
          </div>
          <div style={{ marginTop: 4, fontSize: '0.85rem', color: 'rgba(255,255,255,.72)', lineHeight: 1.35 }}>
            ①右上の「…」→「Safariで開く」<br />
            ②Safariで「共有」→「ホーム画面に追加」
          </div>

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
            <button
              type="button"
              onClick={copyUrl}
              style={{
                padding: '0.42rem 0.85rem',
                borderRadius: 9999,
                border: '1px solid rgba(255,255,255,.14)',
                background: 'rgba(255,255,255,.08)',
                color: 'rgba(255,255,255,.92)',
                fontSize: '0.85rem',
                cursor: 'pointer',
              }}
            >
              URLをコピー
            </button>
            <button
              type="button"
              onClick={close}
              style={{
                padding: '0.42rem 0.85rem',
                borderRadius: 9999,
                border: '1px solid rgba(255,255,255,.10)',
                background: 'rgba(0,0,0,.18)',
                color: 'rgba(255,255,255,.80)',
                fontSize: '0.85rem',
                cursor: 'pointer',
              }}
            >
              今はしない
            </button>
          </div>
        </div>

        <button
          type="button"
          onClick={close}
          aria-label="閉じる"
          style={{
            border: 'none',
            background: 'transparent',
            color: 'rgba(255,255,255,.78)',
            cursor: 'pointer',
            padding: 6,
            borderRadius: 10,
            fontSize: '1.1rem',
            lineHeight: 1,
            flexShrink: 0,
          }}
        >
          ✕
        </button>
      </div>
    </div>
  );
};