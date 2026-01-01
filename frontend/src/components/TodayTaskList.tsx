// frontend/src/components/TodayTaskList.tsx

import { useMemo } from 'react';
import { Task } from '../types';
import { TaskList } from './TaskList';

type TaskNotificationOptions = {
  morning: boolean;
  offsetsHours: number[];
};

interface TodayTaskListProps {
  tasks: Task[];
  onTaskUpdated: () => void;
  onTaskPatched?: (taskId: number, patch: Partial<Task>) => void;
  onTasksRemoved?: (ids: number[]) => void;
  // 親コンポーネント（Dashboard）と共有する通知ON/OFF状態
  notifyOverrides: Record<number, boolean>;
  onNotifyChange: (taskId: number, value: boolean) => void;
  taskNotificationOverrides: Record<number, TaskNotificationOptions>;
  onTaskNotificationOptionsChange: (
    taskId: number,
    value: TaskNotificationOptions
  ) => void;
}

export const TodayTaskList: React.FC<TodayTaskListProps> = ({
  tasks,
  onTaskUpdated,
  onTaskPatched,
  onTasksRemoved,
  notifyOverrides,
  onNotifyChange,
  taskNotificationOverrides,
  onTaskNotificationOptionsChange,
}) => {
  // 今日タスクの達成率だけは Today 専用で計算しておく
  const { percent, doneCount, totalCount } = useMemo(() => {
    const total = tasks.length;
    const done = tasks.filter((t) => t.is_done).length;
    const pct = total === 0 ? 0 : Math.round((done / total) * 100);
    return { percent: pct, doneCount: done, totalCount: total };
  }, [tasks]);

  return (
    <>
      <style>{`
        @keyframes gaugeSheen {
          0% { transform: translateX(-40%); opacity: .0; }
          25% { opacity: .35; }
          50% { transform: translateX(40%); opacity: .0; }
          100% { transform: translateX(40%); opacity: .0; }
        }
        @keyframes gaugePulse {
          0%, 100% { filter: brightness(1) saturate(1); }
          50% { filter: brightness(1.08) saturate(1.1); }
        }
        @keyframes gaugeScan {
          0% { background-position: 0 0; opacity: .22; }
          100% { background-position: 120px 0; opacity: .22; }
        }
        @media (prefers-reduced-motion: reduce) {
          .gauge-sheen, .gauge-pulse, .gauge-scan { animation: none !important; }
        }
      `}</style>
      <div>
        <ProgressGauge
          percent={percent}
          doneCount={doneCount}
          totalCount={totalCount}
        />

        {/* 一覧部分は全部 TaskList に任せるので、
            「全部タブ」と全く同じ UI / 挙動になる */}
        <div style={{ marginTop: '1rem' }}>
          <TaskList
            tasks={tasks}
            onTaskUpdated={onTaskUpdated}
            onTaskPatched={onTaskPatched}
            onTasksRemoved={onTasksRemoved}
            notifyOverrides={notifyOverrides}
            onNotifyChange={onNotifyChange}
            taskNotificationOverrides={taskNotificationOverrides}
            onTaskNotificationOptionsChange={onTaskNotificationOptionsChange}
          />
        </div>
      </div>
    </>
  );
};

const ProgressGauge: React.FC<{
  percent: number;
  doneCount: number;
  totalCount: number;
}> = ({ percent, doneCount, totalCount }) => {
  return (
    <div
      style={{
        marginBottom: '1rem',
        padding: '0.9rem 1rem',
        borderRadius: 16,
        background: 'linear-gradient(135deg, rgba(2,6,23,0.92), rgba(15,23,42,0.86))',
        border: '1px solid rgba(56,189,248,0.14)',
        boxShadow: '0 18px 46px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.06)',
        color: '#e5e7eb',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginBottom: '0.5rem',
          fontSize: '0.9rem',
        }}
      >
        <span>今日のタスク達成率</span>
        <span>
          {doneCount} / {totalCount} 件
        </span>
      </div>
      <div
        style={{
          width: '100%',
          height: 18,
          borderRadius: 9999,
          background:
            'linear-gradient(180deg, rgba(2,6,23,0.55), rgba(15,23,42,0.85))',
          border: '1px solid rgba(56,189,248,0.18)',
          overflow: 'hidden',
          position: 'relative',
          boxShadow:
            'inset 0 2px 10px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.06)',
        }}
      >
        {/* scanline（近未来の薄い走査） */}
        <div
          aria-hidden
          className="gauge-scan"
          style={{
            position: 'absolute',
            inset: 0,
            backgroundImage:
              'linear-gradient(90deg, rgba(56,189,248,0.0) 0%, rgba(56,189,248,0.10) 50%, rgba(56,189,248,0.0) 100%)',
            backgroundSize: '120px 100%',
            animation: 'gaugeScan 3.2s linear infinite',
            mixBlendMode: 'screen',
            pointerEvents: 'none',
          }}
        />

        {/* fill（実ゲージ） */}
        <div
          className="gauge-pulse"
          style={{
            width: `${percent}%`,
            height: '100%',
            borderRadius: 9999,
            background:
              'linear-gradient(90deg, rgba(56,189,248,0.75), rgba(59,130,246,0.92), rgba(37,99,235,0.88))',
            position: 'relative',
            transition: 'width 240ms ease-out',
            boxShadow:
              '0 10px 26px rgba(37,99,235,0.28), inset 0 1px 0 rgba(255,255,255,0.16)',
            animation: percent > 0 ? 'gaugePulse 2.8s ease-in-out infinite' : undefined,
          }}
        >
          {/* sheen（立体的なハイライトが流れる） */}
          <div
            aria-hidden
            className="gauge-sheen"
            style={{
              position: 'absolute',
              inset: 0,
              background:
                'linear-gradient(120deg, transparent 0%, rgba(255,255,255,0.22) 45%, transparent 70%)',
              transform: 'translateX(-40%)',
              animation:
                percent > 0 ? 'gaugeSheen 2.6s ease-in-out infinite' : undefined,
              mixBlendMode: 'screen',
              pointerEvents: 'none',
            }}
          />

          {/* top highlight（上面の薄い反射） */}
          <div
            aria-hidden
            style={{
              position: 'absolute',
              left: 0,
              right: 0,
              top: 0,
              height: 6,
              background: 'linear-gradient(180deg, rgba(255,255,255,0.22), transparent)',
              opacity: 0.55,
              pointerEvents: 'none',
            }}
          />
        </div>
      </div>
      <div
        style={{
          marginTop: 4,
          textAlign: 'center',
          fontSize: '0.85rem',
          fontWeight: 600,
        }}
      >
        {percent}%
      </div>
    </div>
  );
};
