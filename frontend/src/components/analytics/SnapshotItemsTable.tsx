// frontend/src/components/analytics/SnapshotItemsTable.tsx

import React, { useMemo, useState } from 'react';
import { ActionEffectivenessItem } from '../../api/analyticsActions';

type RankRow = { rank: number; improved: number; measured: number };

type Props = {
  snapshotId: number;
  items: ActionEffectivenessItem[];
  currentRankMap: Map<string, RankRow>;
  previousRankMap: Map<string, RankRow> | null;
  hasPreviousSnapshot: boolean;
};

const LOW_SAMPLE_THRESHOLD = 10;

export const SnapshotItemsTable: React.FC<Props> = ({
  snapshotId,
  items,
  currentRankMap,
  previousRankMap,
  hasPreviousSnapshot,
}) => {
  // ✅ Priority 5: 全件表示（折りたたみ）
  const [showAll, setShowAll] = useState(false);
  const [viewMode, setViewMode] = useState<'cards' | 'table'>('cards');

  // ✅ 毎レンダーで sort + slice しない（監査資産は同じでもUIは軽くする）
  const sortedItems = useMemo(() => {
    return [...(items ?? [])].sort((a, b) => {
      const ar = Number(a.improved_rate ?? 0);
      const br = Number(b.improved_rate ?? 0);
      if (br !== ar) return br - ar;
      return Number(b.measured_count ?? 0) - Number(a.measured_count ?? 0);
    });
  }, [items]);

  const visibleItems = showAll ? sortedItems : sortedItems.slice(0, 8);

  return (
    <div style={{ marginTop: '0.6rem', display: 'grid', gap: '0.35rem' }}>
      {/* ✅ トグルUI（Top8 / 全件） */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ fontSize: '0.8rem', opacity: 0.75 }}>
            表示: {showAll ? `全件（${sortedItems.length}件）` : `Top8（${Math.min(8, sortedItems.length)} / ${sortedItems.length}件）`}
            {'  '} / view: {viewMode}
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button
            type="button"
            onClick={() => setViewMode((v) => (v === 'cards' ? 'table' : 'cards'))}
            style={{
                fontSize: '0.8rem',
                padding: '0.25rem 0.5rem',
                borderRadius: 10,
                border: '1px solid rgba(255,255,255,.14)',
                background: 'rgba(255,255,255,.04)',
                cursor: 'pointer',
            }}
            >
            {viewMode === 'cards' ? 'Table view' : 'Cards view'}
            </button>

            {sortedItems.length > 8 && (
            <button
                type="button"
                onClick={() => setShowAll((v) => !v)}
                style={{
                fontSize: '0.8rem',
                padding: '0.25rem 0.5rem',
                borderRadius: 10,
                border: '1px solid rgba(255,255,255,.14)',
                background: 'rgba(255,255,255,.04)',
                cursor: 'pointer',
                }}
            >
                {showAll ? 'Top8に戻す' : '全件表示'}
            </button>
            )}
        </div>
      </div>

      {viewMode === 'table' ? (
        <div
            style={{
            border: '1px solid rgba(255,255,255,.10)',
            borderRadius: 12,
            overflow: 'hidden',
            background: 'rgba(255,255,255,.03)',
            }}
        >
            <div
            style={{
                display: 'grid',
                gridTemplateColumns: '2.2fr 1fr 1fr 1fr 1.1fr 1.2fr 1.2fr',
                gap: 8,
                padding: '0.45rem 0.6rem',
                fontSize: '0.75rem',
                fontWeight: 800,
                opacity: 0.82,
                borderBottom: '1px solid rgba(255,255,255,.10)',
            }}
            >
            <div>action</div>
            <div>improved%</div>
            <div>measured</div>
            <div>applied</div>
            <div>Δrank</div>
            <div>Δrate</div>
            <div>avgΔmissed</div>
            </div>

            {visibleItems.map((x) => {
            const key = String(x.action_id);
            const cur = currentRankMap.get(key) ?? null;
            const prev = previousRankMap?.get(key) ?? null;

            const isLowSample = Number(x.measured_count ?? 0) < LOW_SAMPLE_THRESHOLD;
            const dRank = prev && cur ? prev.rank - cur.rank : null;
            const dRate = prev && cur ? (cur.improved - prev.improved) * 100 : null;

            const fmtSigned = (n: number, digits = 1) => {
                const p = Math.pow(10, digits);
                const v = Math.round(n * p) / p;
                return `${v >= 0 ? '+' : ''}${v}`;
            };
            const fmtSignedInt = (n: number) => `${n >= 0 ? '+' : ''}${n}`;

            const improvedPct = Math.round(Number(x.improved_rate ?? 0) * 1000) / 10;

            return (
                <div
                key={`snap-${snapshotId}-${x.action_id}`}
                style={{
                    display: 'grid',
                    gridTemplateColumns: '2.2fr 1fr 1fr 1fr 1.1fr 1.2fr 1.2fr',
                    gap: 8,
                    padding: '0.45rem 0.6rem',
                    fontSize: '0.78rem',
                    borderBottom: '1px solid rgba(255,255,255,.06)',
                    opacity: isLowSample ? 0.55 : 1,
                }}
                >
                <div style={{ fontWeight: 750, display: 'flex', alignItems: 'center', gap: 6 }}>
                    {isLowSample && (
                    <span
                        title={`measured_count < ${LOW_SAMPLE_THRESHOLD}（サンプル数が少ないため信頼度低）`}
                        style={{ color: '#f5c542', fontSize: '0.85rem' }}
                    >
                        ⚠️
                    </span>
                    )}
                    {x.action_id}
                </div>

                <div style={{ opacity: 0.9 }}>{improvedPct}%</div>
                <div style={{ opacity: 0.9 }}>{Number(x.measured_count ?? 0)}</div>
                <div style={{ opacity: 0.9 }}>{Number(x.applied_count ?? 0)}</div>

                <div style={{ opacity: 0.9 }}>
                    {!hasPreviousSnapshot || !prev || !cur ? '—' : fmtSignedInt(dRank ?? 0)}
                </div>
                <div style={{ opacity: 0.9 }}>
                    {!hasPreviousSnapshot || !prev || !cur ? '—' : `${fmtSigned(dRate ?? 0, 1)}%`}
                </div>
                <div style={{ opacity: 0.9 }}>{Number(x.avg_delta_missed_rate ?? 0)}</div>
                </div>
            );
            })}
        </div>
        ) : (
        // ✅ Cards view（今のまま）
        <>
            {visibleItems.map((x) => {
            const key = String(x.action_id);
            const cur = currentRankMap.get(key) ?? null;
            const prev = previousRankMap?.get(key) ?? null;
            const isLowSample = Number(x.measured_count ?? 0) < LOW_SAMPLE_THRESHOLD;
            const dRank = prev && cur ? prev.rank - cur.rank : null;
            const dRate = prev && cur ? (cur.improved - prev.improved) * 100 : null;

            const fmtSigned = (n: number, digits = 1) => {
                const p = Math.pow(10, digits);
                const v = Math.round(n * p) / p;
                return `${v >= 0 ? '+' : ''}${v}`;
            };
            const fmtSignedInt = (n: number) => `${n >= 0 ? '+' : ''}${n}`;

            return (
              <div
                key={`snap-${snapshotId}-${x.action_id}`}
                style={{
                    padding: '0.55rem 0.65rem',
                    borderRadius: 12,
                    border: '1px solid rgba(255,255,255,.10)',
                    background: 'rgba(255,255,255,.03)',
                    opacity: isLowSample ? 0.55 : 1,
                }}
              >
                <div style={{ fontWeight: 750, display: 'flex', alignItems: 'center', gap: 6 }}>
                    {isLowSample && (
                    <span
                        title={`measured_count < ${LOW_SAMPLE_THRESHOLD}（サンプル数が少ないため信頼度低）`}
                        style={{ color: '#f5c542', fontSize: '0.85rem' }}
                    >
                        ⚠️
                    </span>
                    )}
                    {x.action_id}
                </div>

                {!hasPreviousSnapshot || !prev || !cur ? (
                    <div style={{ marginTop: '0.25rem', fontSize: '0.75rem', opacity: 0.7 }}>
                    （前回比較なし）
                    </div>
                ) : (
                    <div style={{ marginTop: '0.25rem', fontSize: '0.75rem', opacity: 0.82 }}>
                    Δrank: {fmtSignedInt(dRank ?? 0)}（prev {prev.rank} → now {cur.rank}）
                    {'  '} / Δrate: {fmtSigned(dRate ?? 0, 1)}%
                    {'  '}（prev {Math.round(prev.improved * 1000) / 10}% → now {Math.round(cur.improved * 1000) / 10}%）
                    </div>
                )}
                <div style={{ opacity: 0.8 }}>
                    improved_rate: {Math.round(Number(x.improved_rate ?? 0) * 1000) / 10}%
                    {'  '} / measured: {Number(x.measured_count ?? 0)}
                    {'  '} / applied: {Number(x.applied_count ?? 0)}
                    {'  '} / avgΔmissed: {Number(x.avg_delta_missed_rate ?? 0)}
                </div>
              </div>
            );
          })}
        </>
      )}
    </div>
  );
};
