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
          0% { transform: translateX(-55%); opacity: 0; }
          18% { opacity: .45; }
          45% { transform: translateX(55%); opacity: 0; }
          100% { transform: translateX(55%); opacity: 0; }
        }

        @keyframes gaugePulse {
          0%, 100% { filter: brightness(1) saturate(1); }
          50% { filter: brightness(1.12) saturate(1.18); }
        }

        @keyframes gaugeScan {
          0% { background-position: 0 0; opacity: .18; }
          100% { background-position: 160px 0; opacity: .18; }
        }

        /* “粒子/線”っぽい背景をゆっくり流す */
        @keyframes gaugeConstellationDrift {
          0% { transform: translate3d(-2%, -1%, 0) scale(1); opacity: .22; }
          50% { transform: translate3d(2%, 1%, 0) scale(1.02); opacity: .28; }
          100% { transform: translate3d(-2%, -1%, 0) scale(1); opacity: .22; }
        }

        /* 点滅（粒子の“生きてる感”） */
        @keyframes gaugeTwinkle {
          0%, 100% { opacity: .22; }
          50% { opacity: .42; }
        }

        /* 立体っぽい“内側の陰影”を呼吸 */
        @keyframes gaugeDepthBreath {
          0%, 100% { opacity: .55; }
          50% { opacity: .72; }
        }

        @media (prefers-reduced-motion: reduce) {
          .gauge-sheen, .gauge-pulse, .gauge-scan,
          .gauge-constellation, .gauge-twinkle, .gauge-depth {
            animation: none !important;
          }
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
  const hasProgress = percent > 0;

  return (
    <div
      style={{
        marginBottom: '1rem',
        padding: '0.95rem 1rem',
        borderRadius: 18,
        position: 'relative',
        overflow: 'hidden',
        background:
          'linear-gradient(135deg, rgba(2,6,23,0.92), rgba(15,23,42,0.86))',
        border: '1px solid rgba(56,189,248,0.18)',
        boxShadow:
          '0 22px 60px rgba(0,0,0,0.48), inset 0 1px 0 rgba(255,255,255,0.06)',
        color: '#e5e7eb',
      }}
    >
      {/* 近未来 “粒子/線” っぽい背景（ログインの雰囲気をカード内に移植） */}
      <div
        aria-hidden
        className="gauge-constellation"
        style={{
          position: 'absolute',
          inset: -40,
          pointerEvents: 'none',
          mixBlendMode: 'screen',
          animation: 'gaugeConstellationDrift 7.2s ease-in-out infinite',
          backgroundImage: `
            /* dots */
            radial-gradient(circle at 12% 28%, rgba(56,189,248,0.55) 0 2px, transparent 3px),
            radial-gradient(circle at 22% 62%, rgba(56,189,248,0.42) 0 2px, transparent 3px),
            radial-gradient(circle at 38% 18%, rgba(56,189,248,0.38) 0 2px, transparent 3px),
            radial-gradient(circle at 58% 42%, rgba(56,189,248,0.46) 0 2px, transparent 3px),
            radial-gradient(circle at 74% 24%, rgba(56,189,248,0.40) 0 2px, transparent 3px),
            radial-gradient(circle at 82% 66%, rgba(56,189,248,0.48) 0 2px, transparent 3px),

            /* lines */
            linear-gradient(115deg, transparent 0%, rgba(56,189,248,0.16) 46%, transparent 52%),
            linear-gradient(35deg,  transparent 0%, rgba(56,189,248,0.12) 46%, transparent 52%),
            linear-gradient(165deg, transparent 0%, rgba(56,189,248,0.10) 46%, transparent 52%)
          `,
          filter: 'blur(0.2px)',
          opacity: 0.28,
        }}
      />

      {/* 粒子の点滅（もう1枚重ねて“動いてる感”を増やす） */}
      <div
        aria-hidden
        className="gauge-twinkle"
        style={{
          position: 'absolute',
          inset: -20,
          pointerEvents: 'none',
          mixBlendMode: 'screen',
          animation: 'gaugeTwinkle 3.6s ease-in-out infinite',
          backgroundImage: `
            radial-gradient(circle at 18% 40%, rgba(147,197,253,0.35) 0 1.5px, transparent 3px),
            radial-gradient(circle at 44% 68%, rgba(147,197,253,0.28) 0 1.5px, transparent 3px),
            radial-gradient(circle at 66% 34%, rgba(147,197,253,0.30) 0 1.5px, transparent 3px),
            radial-gradient(circle at 86% 48%, rgba(147,197,253,0.26) 0 1.5px, transparent 3px)
          `,
          opacity: 0.28,
        }}
      />

      {/* カードの“内側陰影”で立体感を増やす */}
      <div
        aria-hidden
        className="gauge-depth"
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          animation: 'gaugeDepthBreath 4.8s ease-in-out infinite',
          background:
            'radial-gradient(110% 90% at 18% 12%, rgba(56,189,248,0.20) 0%, transparent 55%), radial-gradient(120% 100% at 88% 68%, rgba(37,99,235,0.18) 0%, transparent 55%)',
          opacity: 0.62,
          mixBlendMode: 'screen',
        }}
      />

      {/* header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginBottom: '0.55rem',
          fontSize: '0.9rem',
          position: 'relative',
          zIndex: 1,
        }}
      >
        <span>今日のタスク達成率</span>
        <span>
          {doneCount} / {totalCount} 件
        </span>
      </div>

      {/* bar shell */}
      <div
        style={{
          width: '100%',
          height: 18,
          borderRadius: 9999,
          overflow: 'hidden',
          position: 'relative',
          zIndex: 1,

          /* “筒”っぽい質感（上が明るい/下が暗い） */
          background:
            'linear-gradient(180deg, rgba(2,6,23,0.35) 0%, rgba(15,23,42,0.92) 100%)',
          border: '1px solid rgba(56,189,248,0.22)',
          boxShadow:
            'inset 0 2px 12px rgba(0,0,0,0.58), inset 0 1px 0 rgba(255,255,255,0.08)',
        }}
      >
        {/* scanline */}
        <div
          aria-hidden
          className="gauge-scan"
          style={{
            position: 'absolute',
            inset: 0,
            backgroundImage:
              'linear-gradient(90deg, rgba(56,189,248,0.0) 0%, rgba(56,189,248,0.12) 50%, rgba(56,189,248,0.0) 100%)',
            backgroundSize: '160px 100%',
            animation: 'gaugeScan 2.8s linear infinite',
            mixBlendMode: 'screen',
            pointerEvents: 'none',
          }}
        />

        {/* base inner highlight */}
        <div
          aria-hidden
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            top: 0,
            height: 6,
            background:
              'linear-gradient(180deg, rgba(255,255,255,0.18) 0%, transparent 100%)',
            opacity: 0.65,
            pointerEvents: 'none',
          }}
        />

        {/* fill */}
        <div
          className="gauge-pulse"
          style={{
            width: `${percent}%`,
            height: '100%',
            borderRadius: 9999,
            position: 'relative',
            transition: 'width 260ms ease-out',

            /* 3Dっぽい色（シアン→ブルー→ディープブルー） */
            background:
              'linear-gradient(90deg, rgba(56,189,248,0.82), rgba(59,130,246,0.95), rgba(37,99,235,0.90))',

            boxShadow:
              '0 10px 28px rgba(37,99,235,0.30), 0 0 24px rgba(56,189,248,0.18), inset 0 1px 0 rgba(255,255,255,0.18)',

            animation: hasProgress
              ? 'gaugePulse 2.4s ease-in-out infinite'
              : undefined,
          }}
        >
          {/* sheen */}
          <div
            aria-hidden
            className="gauge-sheen"
            style={{
              position: 'absolute',
              inset: 0,
              background:
                'linear-gradient(120deg, transparent 0%, rgba(255,255,255,0.28) 45%, transparent 70%)',
              transform: 'translateX(-55%)',
              animation: hasProgress
                ? 'gaugeSheen 2.2s ease-in-out infinite'
                : undefined,
              mixBlendMode: 'screen',
              pointerEvents: 'none',
            }}
          />

          {/* micro noise / texture（“のっぺり”防止） */}
          <div
            aria-hidden
            style={{
              position: 'absolute',
              inset: 0,
              backgroundImage:
                'linear-gradient(0deg, rgba(255,255,255,0.06) 1px, transparent 1px)',
              backgroundSize: '100% 6px',
              opacity: 0.22,
              mixBlendMode: 'overlay',
              pointerEvents: 'none',
            }}
          />
        </div>
      </div>

      {/* percent */}
      <div
        style={{
          marginTop: 6,
          textAlign: 'center',
          fontSize: '0.85rem',
          fontWeight: 700,
          letterSpacing: 0.4,
          position: 'relative',
          zIndex: 1,
          textShadow: '0 0 10px rgba(56,189,248,0.20)',
        }}
      >
        {percent}%
      </div>
    </div>
  );
};
