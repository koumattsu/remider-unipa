// frontend/src/components/analytics/SnapshotHeader.tsx

import React from 'react';
import { ActionEffectivenessSnapshotItem, ActionAppliedEvent } from '../../api/analyticsActions';

type Props = {
  snapshots: ActionEffectivenessSnapshotItem[];
  selectedSnapshotId: number | null;
  onSelect: (id: number | null) => void;
  current: ActionEffectivenessSnapshotItem;
  previous: ActionEffectivenessSnapshotItem | null;
  asOfApplied: ActionAppliedEvent | null;
};

export const SnapshotHeader: React.FC<Props> = ({
  snapshots,
  selectedSnapshotId,
  onSelect,
  current,
  previous,
  asOfApplied,
}) => {
  return (
    <>
      {/* snapshot select */}
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.5rem' }}>
        <div style={{ fontSize: '0.82rem', fontWeight: 800, opacity: 0.9 }}>
          snapshot:
        </div>
        <select
          value={selectedSnapshotId ?? current.id}
          onChange={(e) => {
            const n = Number(e.target.value);
            onSelect(Number.isFinite(n) ? n : null);
          }}
          style={{
            flex: 1,
            padding: '0.45rem 0.6rem',
            borderRadius: 12,
            border: '1px solid rgba(255,255,255,.12)',
            background: 'rgba(255,255,255,.06)',
            color: 'rgba(255,255,255,.92)',
            fontWeight: 800,
            outline: 'none',
          }}
        >
          {snapshots.map((s) => (
            <option key={s.id} value={s.id}>
              {new Date(s.computed_at).toLocaleString()}（{s.bucket} / {s.items.length} actions / {s.range.window_days}d）
            </option>
          ))}
        </select>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', marginBottom: '0.25rem' }}>
        <div style={{ fontWeight: 900 }}>
          snapshot #{current.id}（{current.bucket}）
        </div>
        <div style={{ fontWeight: 800, opacity: 0.85 }}>
          computed_at: {new Date(current.computed_at).toLocaleString()}
        </div>
      </div>

      {previous && (
        <div style={{ marginTop: '0.15rem', fontSize: '0.75rem', opacity: 0.72 }}>
          compare_to: snapshot #{previous.id} / computed_at: {new Date(previous.computed_at).toLocaleString()}
        </div>
      )}

      <div style={{ opacity: 0.75 }}>
        window_days: {current.range.window_days} / min_total: {current.range.min_total} / limit_events: {current.range.limit_events}
      </div>

      {(current.range.from || current.range.to || current.range.timezone) && (
        <div style={{ marginTop: '0.25rem', fontSize: '0.75rem', opacity: 0.72 }}>
          range:
          {current.range.from ? ` from ${new Date(current.range.from).toLocaleString()}` : ''}
          {current.range.to ? ` to ${new Date(current.range.to).toLocaleString()}` : ''}
          {current.range.timezone ? `（tz: ${current.range.timezone}）` : ''}
        </div>
      )}

      <div style={{ marginTop: '0.35rem', opacity: 0.8 }}>
        actions: {current.items.length} 件
      </div>
      {/* ✅ 監査用の注記（UIは資産を再計算しない／見せ方だけ） */}
      <div
        style={{
            marginTop: '0.35rem',
            fontSize: '0.75rem',
            opacity: 0.72,
            padding: '0.45rem 0.6rem',
            borderRadius: 10,
            border: '1px solid rgba(255,255,255,.10)',
            background: 'rgba(255,255,255,.03)',
            lineHeight: 1.55,
        }}
      >
        <div style={{ fontWeight: 800, opacity: 0.85, marginBottom: '0.15rem' }}>注記（監査）</div>
        <div>・この画面は snapshot 資産を <strong>再計算しません</strong>（表示のみ）。</div>
        <div>
            ・前回比較（compare_to）は <strong>同じ bucket</strong> かつ <strong>computed_at が直前</strong> の snapshot のみ（存在しない場合は「前回比較なし」）。
        </div>
        <div>
            ・⚠️ / 透明度の低下は <strong>measured_count &lt; 10</strong>（サンプル数が少なく信頼度が低い可能性）。
        </div>
      </div>
      {asOfApplied && (
        <div
            style={{
            marginTop: '0.35rem',
            fontSize: '0.75rem',
            opacity: 0.75,
            padding: '0.35rem 0.5rem',
            borderRadius: 10,
            border: '1px solid rgba(255,255,255,.10)',
            background: 'rgba(255,255,255,.03)',
            }}
        >
            as of snapshot:
            <strong style={{ marginLeft: 4 }}>{asOfApplied.action_id}</strong>
            {' '}applied at{' '}
            {new Date(asOfApplied.applied_at).toLocaleString()}
        </div>
        )}
    </>
  );
};
