// frontend/src/components/StatsView.tsx
import { useEffect, useMemo, useState } from 'react';
import { outcomesApi, OutcomeLog } from '../api/outcomes';
import { Task } from '../types'; // 既存props互換のため残す（不要なら後で消せる）

interface StatsViewProps {
  tasks: Task[]; // 互換のため残す（今後 outcomes だけにするなら削除OK）
}

export const StatsView: React.FC<StatsViewProps> = ({ tasks: _tasks }) => {
  const [logs, setLogs] = useState<OutcomeLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        setLoading(true);
        setError(null);
        // まずは全件取得（重くなったら from/to で絞る）
        const data = await outcomesApi.list();
        if (!mounted) return;
        setLogs(data);
      } catch (e: any) {
        if (!mounted) return;
        setError(e?.message ?? 'failed to load outcomes');
      } finally {
        if (!mounted) return;
        setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfWeek = new Date(startOfToday);
  startOfWeek.setDate(startOfWeek.getDate() - 6); // 過去7日
  const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
  const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0);

  const parseDeadline = (x: OutcomeLog) => new Date(x.deadline);

  const inRange = (d: Date, from: Date, to: Date) =>
    d.getTime() >= from.getTime() && d.getTime() <= to.getTime();

  const weeklyLogs = useMemo(
    () => logs.filter((x) => inRange(parseDeadline(x), startOfWeek, startOfToday)),
    [logs, startOfWeek, startOfToday]
  );

  const monthlyLogs = useMemo(
    () => logs.filter((x) => inRange(parseDeadline(x), startOfMonth, endOfMonth)),
    [logs, startOfMonth, endOfMonth]
  );

  const calcRate = (subset: OutcomeLog[]) => {
    const total = subset.length;
    if (total === 0) return { total: 0, done: 0, rate: 0 };
    const done = subset.filter((x) => x.outcome === 'done').length;
    return { total, done, rate: Math.round((done / total) * 100) };
  };

  const weekly = useMemo(() => calcRate(weeklyLogs), [weeklyLogs]);
  const monthly = useMemo(() => calcRate(monthlyLogs), [monthlyLogs]);

  if (loading) {
    return <div style={{ color: 'rgba(255,255,255,.7)' }}>Loading…</div>;
  }
  if (error) {
    return <div style={{ color: '#fca5a5' }}>Failed: {error}</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <StatsCard
        title="今週（直近7日）の達成率"
        subtitle="OutcomeLog（締切到達時点の結果）ベース"
        rate={weekly.rate}
        total={weekly.total}
        done={weekly.done}
      />
      <StatsCard
        title="今月の達成率"
        subtitle="OutcomeLog（締切到達時点の結果）ベース"
        rate={monthly.rate}
        total={monthly.total}
        done={monthly.done}
      />
    </div>
  );
};

interface StatsCardProps {
  title: string;
  subtitle: string;
  rate: number;
  total: number;
  done: number;
}

const StatsCard: React.FC<StatsCardProps> = ({ title, subtitle, rate, total, done }) => {
  const clampedRate = Math.max(0, Math.min(100, rate));

  // ✅ 近未来（ガラス感）に寄せる
  return (
    <div
      style={{
        padding: '1rem 1.1rem',
        borderRadius: 18,
        border: '1px solid rgba(255,255,255,.12)',
        background:
          'radial-gradient(circle at 20% 0%, rgba(0,212,255,.18), rgba(255,255,255,.06) 45%, rgba(255,255,255,.04))',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        boxShadow: '0 14px 40px rgba(0,0,0,.38)',
        color: 'rgba(255,255,255,.92)',
      }}
    >
      <div style={{ marginBottom: '0.25rem', fontWeight: 800, letterSpacing: '0.02em' }}>
        {title}
      </div>
      <div style={{ marginBottom: '0.75rem', fontSize: '0.8rem', color: 'rgba(255,255,255,.62)' }}>
        {subtitle}
      </div>

      <div
        style={{
          position: 'relative',
          height: 16,
          borderRadius: 9999,
          backgroundColor: 'rgba(255,255,255,.10)',
          overflow: 'hidden',
          marginBottom: '0.35rem',
        }}
      >
        <div
          style={{
            width: `${clampedRate}%`,
            height: '100%',
            borderRadius: 9999,
            background: 'linear-gradient(90deg, rgba(34,197,94,.95), rgba(14,165,233,.95))',
            transition: 'width 0.25s ease-out',
          }}
        />
      </div>

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '0.85rem',
          color: 'rgba(255,255,255,.78)',
        }}
      >
        <span>{clampedRate}% 達成</span>
        <span>
          {done} / {total} 件
        </span>
      </div>
    </div>
  );
};