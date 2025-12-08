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
          notifyOverrides={notifyOverrides}
          onNotifyChange={onNotifyChange}
          taskNotificationOverrides={taskNotificationOverrides}
          onTaskNotificationOptionsChange={onTaskNotificationOptionsChange}
        />
      </div>
    </div>
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
        background: 'linear-gradient(90deg, #020617, #0f172a)',
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
          height: 16,
          borderRadius: 9999,
          backgroundColor: '#0f172a',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${percent}%`,
            height: '100%',
            borderRadius: 9999,
            background: 'linear-gradient(90deg, #22c55e, #0ea5e9)',
            transition: 'width 0.2s ease-out',
          }}
        />
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
