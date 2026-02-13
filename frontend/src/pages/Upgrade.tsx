// frontend/src/pages/Upgrade.tsx

import React from 'react';

export const Upgrade: React.FC = () => {
  return (
    <div style={{ paddingBottom: '4rem' }}>
      <h1 style={{ marginBottom: '0.75rem' }}>DueFlow Pro</h1>

      <div
        style={{
          borderRadius: 18,
          border: '1px solid rgba(255,255,255,.12)',
          background: 'rgba(255,255,255,.04)',
          padding: '0.9rem',
          lineHeight: 1.5,
        }}
      >
        <div style={{ fontWeight: 800, marginBottom: '0.5rem' }}>
          できるようになること
        </div>

        <ul style={{ margin: 0, paddingLeft: '1.2rem', opacity: 0.9 }}>
          <li>タスクごとに「締切の◯時間前通知」を複数追加</li>
          <li>通知タイミングを自分の生活に合わせて最適化</li>
          <li>（将来）WebPush / LINE など配信チャネル選択</li>
        </ul>

        <div style={{ marginTop: '0.75rem', opacity: 0.75, fontSize: '0.85rem' }}>
          ※ 現在この画面は準備中です（課金機構は後で実装します）
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.9rem' }}>
          <button
            type="button"
            onClick={() => {
              // ✅ 最小：元の画面に戻す（HashRouter想定）
              window.location.hash = '/dashboard?tab=all';
            }}
            style={{
              padding: '0.5rem 0.75rem',
              borderRadius: '0.9rem',
              border: '1px solid rgba(255,255,255,.15)',
              background: 'rgba(255,255,255,.06)',
              color: 'white',
              cursor: 'pointer',
            }}
          >
            ← 戻る
          </button>

          <button
            type="button"
            onClick={() => {
              alert('準備中です（ここに購入フローを後で接続します）');
            }}
            style={{
              padding: '0.5rem 0.85rem',
              borderRadius: '0.9rem',
              border: 'none',
              background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
              color: 'white',
              fontWeight: 800,
              cursor: 'pointer',
            }}
          >
            Proにする（準備中）
          </button>
        </div>
      </div>
    </div>
  );
};