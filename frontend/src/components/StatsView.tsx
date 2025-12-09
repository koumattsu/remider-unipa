// frontend/src/components/StatsView.tsx

import { Task } from '../types';

interface StatsViewProps {
  tasks: Task[];
}

export const StatsView: React.FC<StatsViewProps> = ({ tasks }) => {
  const now = new Date();

  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfWeek = new Date(startOfToday);
  startOfWeek.setDate(startOfWeek.getDate() - 6); // 過去7日分

  const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
  const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0);

  const inRange = (d: Date, from: Date, to: Date) =>
    d.getTime() >= from.getTime() && d.getTime() <= to.getTime();

  const parseDeadline = (t: Task) => new Date(t.deadline);

  const weeklyTasks = tasks.filter((t) =>
    inRange(parseDeadline(t), startOfWeek, startOfToday)
  );
  const monthlyTasks = tasks.filter((t) =>
    inRange(parseDeadline(t), startOfMonth, endOfMonth)
  );

  const calcRate = (subset: Task[]) => {
    if (subset.length === 0) return { total: 0, done: 0, rate: 0 };
    const done = subset.filter((t) => t.is_done).length;
    return {
      total: subset.length,
      done,
      rate: Math.round((done / subset.length) * 100),
    };
  };

  const weekly = calcRate(weeklyTasks);
  const monthly = calcRate(monthlyTasks);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <StatsCard
        title="今週（直近7日）の達成率"
        subtitle="締切が過去7日間の課題ベース"
        rate={weekly.rate}
        total={weekly.total}
        done={weekly.done}
      />
      <StatsCard
        title="今月の達成率"
        subtitle="今月締切の課題ベース"
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

const StatsCard: React.FC<StatsCardProps> = ({
  title,
  subtitle,
  rate,
  total,
  done,
}) => {
  const clampedRate = Math.max(0, Math.min(100, rate));

  return (
    <div
      style={{
        padding: '1rem 1.2rem',
        borderRadius: '12px',
        border: '1px solid #ddd',
        backgroundColor: '#fafafa',
      }}
    >
      <div style={{ marginBottom: '0.25rem', fontWeight: 600 }}>{title}</div>
      <div style={{ marginBottom: '0.75rem', fontSize: '0.8rem', color: '#777' }}>
        {subtitle}
      </div>
      <div
        style={{
          position: 'relative',
          height: 18,
          borderRadius: 9999,
          backgroundColor: '#e6e6e6',
          overflow: 'hidden',
          marginBottom: '0.35rem',
        }}
      >
        <div
          style={{
            width: `${clampedRate}%`,
            height: '100%',
            background:
              'linear-gradient(90deg, #00c6ff, #0072ff)',
            transition: 'width 0.3s ease',
          }}
        />
      </div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '0.85rem',
          color: '#555',
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
