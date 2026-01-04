// frontend/src/components/analytics/ActionEffectivenessTopList.tsx

import React from 'react';
import { ActionEffectivenessItem } from '../../api/analyticsActions';

type RankRow = { rank: number; improved: number; measured: number };

type Props = {
  snapshotId: number;
  items: ActionEffectivenessItem[];
  currentRankMap: Map<string, RankRow>;
  previousRankMap: Map<string, RankRow> | null;
  hasPreviousSnapshot: boolean;
};

export const ActionEffectivenessTopList: React.FC<Props> = ({
  snapshotId,
  items,
  currentRankMap,
  previousRankMap,
  hasPreviousSnapshot,
}) => {
  const fmtSigned = (n: number, digits = 1) => {
    const x = Math.round(n * Math.pow(10, digits)) / Math.pow(10, digits);
    return `${x >= 0 ? '+' : ''}${x}`;
  };

  const fmtSignedInt = (n: number) => `${n >= 0 ? '+' : ''}${n}`;

  const top = [...(items ?? [])]
    .sort((a, b) => {
      const ar = Number(a.improved_rate ?? 0);
      const br = Number(b.improved_rate ?? 0);
      if (br !== ar) return br - ar;
      return Number(b.measured_count ?? 0) - Number(a.measured_count ?? 0);
    })
    .slice(0, 8);

  return (
    <div style={{ marginTop: '0.6rem', display: 'grid', gap: '0.35rem' }}>
      {top.map((x) => {
        const key = String(x.action_id);
        const cur = currentRankMap.get(key) ?? null;
        const prev = previousRankMap?.get(key) ?? null;

        const dRank = prev && cur ? (prev.rank - cur.rank) : null;
        const dRate = prev && cur ? ((cur.improved - prev.improved) * 100) : null;

        return (
          <div
            key={`snap-${snapshotId}-${x.action_id}`}
            style={{
              padding: '0.55rem 0.65rem',
              borderRadius: 12,
              border: '1px solid rgba(255,255,255,.10)',
              background: 'rgba(255,255,255,.03)',
            }}
          >
            <div style={{ fontWeight: 750 }}>{x.action_id}</div>

            {(!hasPreviousSnapshot || !prev || !cur) ? (
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
    </div>
  );
};
