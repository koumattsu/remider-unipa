// frontend/src/components/TodayTaskList.tsx

import { useState, useMemo } from 'react';
import { Task } from '../types';
import { tasksApi } from '../api/tasks';

// Task.id が負の値のものは「毎週タスク」から生成した仮想タスク
const isVirtualTask = (task: Task) => task.id < 0;


interface TodayTaskListProps {
  tasks: Task[];
  onTaskUpdated: () => void;
  // 親コンポーネント（Dashboard）と共有する通知ON/OFF状態
  notifyOverrides: Record<number, boolean>;
  onNotifyChange: (taskId: number, value: boolean) => void;
}

type LocalState = {
  is_done?: boolean;
  title?: string;
  memo?: string;
};

export const TodayTaskList: React.FC<TodayTaskListProps> = ({
  tasks,
  onTaskUpdated,
  notifyOverrides,
  onNotifyChange,
}) => {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);
  const [localStates, setLocalStates] = useState<Record<number, LocalState>>({});

  const mergeLocal = (id: number, patch: LocalState) => {
    setLocalStates((prev) => ({
      ...prev,
      [id]: { ...prev[id], ...patch },
    }));
  };

  const formatDeadline = (dateString: string) => {
    const date = new Date(dateString);
    const hours = date.getHours();
    const minutes = date.getMinutes();

    // 00:00 は前日の 24:00 表示にする
    if (hours === 0 && minutes === 0) {
      const prev = new Date(date);
      prev.setDate(prev.getDate() - 1);
      const month = String(prev.getMonth() + 1).padStart(2, '0');
      const day = String(prev.getDate()).padStart(2, '0');
      return `${month}/${day} 24:00`;
    }

    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const h = String(hours).padStart(2, '0');
    const m = String(minutes).padStart(2, '0');
    return `${month}/${day} ${h}:${m}`;
  };

  const sortedTasks = useMemo(
    () =>
      [...tasks].sort(
        (a, b) => new Date(a.deadline).getTime() - new Date(b.deadline).getTime()
      ),
    [tasks]
  );

  const { percent, doneCount, totalCount } = useMemo(() => {
    const total = tasks.length;
    const done = tasks.filter((t) => t.is_done).length;
    const pct = total === 0 ? 0 : Math.round((done / total) * 100);
    return { percent: pct, doneCount: done, totalCount: total };
  }, [tasks]);

  // frontend/src/components/TodayTaskList.tsx 内

    const handleToggleDone = async (task: Task, newIsDone: boolean) => {
    // ローカル表示用の is_done 更新
    mergeLocal(task.id, { is_done: newIsDone });

    // ★ 仮タスクはフロント側だけで完了状態＋通知を反映
    if (isVirtualTask(task)) {
      // 未(false) → 完(true)   : !true  = false  → 通知OFF
      // 完(true)  → 未(false)  : !false = true   → 通知ON
      onNotifyChange(task.id, !newIsDone);
      return;
    }

    try {
      await tasksApi.update(task.id, { is_done: newIsDone });
      onTaskUpdated();

      // ★ 進捗に連動して通知も更新
      onNotifyChange(task.id, !newIsDone);
    } catch (error) {
      console.error('タスクの更新に失敗しました:', error);
      alert('タスクの更新に失敗しました');
    }
  };


    const handleTitleSave = async (task: Task, newTitle: string) => {
    const trimmed = newTitle.trim();
    if (!trimmed || trimmed === task.title) return;

    // ★ 仮タスクはテンプレ側で編集する想定なので API は呼ばない
    if (isVirtualTask(task)) {
      mergeLocal(task.id, { title: trimmed });
      return;
    }

    mergeLocal(task.id, { title: trimmed });
    try {
      await tasksApi.update(task.id, { title: trimmed });
      onTaskUpdated();
    } catch (error) {
      console.error('タイトルの更新に失敗しました:', error);
      alert('タイトルの更新に失敗しました');
    }
  };


    const handleMemoSave = async (task: Task, newMemo: string) => {
    const value = newMemo.trim();
    if (value === (task.memo || '')) return;

    // ★ 仮タスクはテンプレ側で編集する想定なので API は呼ばない
    if (isVirtualTask(task)) {
      mergeLocal(task.id, { memo: value });
      return;
    }

    mergeLocal(task.id, { memo: value });
    try {
      await tasksApi.update(task.id, { memo: value });
      onTaskUpdated();
    } catch (error) {
      console.error('内容の更新に失敗しました:', error);
      alert('内容の更新に失敗しました');
    }
  };


  const handleBulkDelete = async () => {
    const realIds = selectedIds.filter((id) => id > 0);
    if (realIds.length === 0) return;

    if (!confirm(`${realIds.length}件のタスクをまとめて削除しますか？`)) return;
    try {
      setIsBulkDeleting(true);
      await Promise.all(realIds.map((id) => tasksApi.delete(id)));
      setSelectedIds([]);
      onTaskUpdated();
    } catch (error) {
      console.error('一括削除に失敗しました:', error);
      alert('タスクの一括削除に失敗しました');
    } finally {
      setIsBulkDeleting(false);
    }
  };

  const toggleSelect = (task: Task) => {
    setSelectedIds((prev) =>
      prev.includes(task.id) ? prev.filter((id) => id !== task.id) : [...prev, task.id]
    );
  };

  const toggleSelectAll = () => {
    if (sortedTasks.length === 0) {
      setSelectedIds([]);
      return;
    }
    const allSelected = sortedTasks.every((t) => selectedIds.includes(t.id));
    if (allSelected) {
      setSelectedIds([]);
    } else {
      setSelectedIds(sortedTasks.map((t) => t.id));
    }
  };

  if (tasks.length === 0) {
    return (
      <div>
        <ProgressGauge percent={0} doneCount={0} totalCount={0} />
        <p style={{ color: '#666', marginTop: '1rem' }}>今日のタスクはありません。</p>
      </div>
    );
  }

  const selectedCount = selectedIds.filter((id) => id > 0).length;

  return (
    <div>
      <ProgressGauge
        percent={percent}
        doneCount={doneCount}
        totalCount={totalCount}
      />

      {/* ラベル「今日のタスク一覧」は削除 */}
      <div
        style={{
          marginTop: '1.25rem',
          marginBottom: '0.75rem',
          display: 'flex',
          justifyContent: 'flex-end',
          alignItems: 'center',
          gap: '1rem',
        }}
      >
        <button
          onClick={handleBulkDelete}
          disabled={selectedCount === 0 || isBulkDeleting}
          style={{
            padding: '0.4rem 0.8rem',
            fontSize: '0.9rem',
            backgroundColor:
              selectedCount === 0 || isBulkDeleting ? '#ccc' : '#dc3545',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor:
              selectedCount === 0 || isBulkDeleting ? 'not-allowed' : 'pointer',
          }}
        >
          {isBulkDeleting
            ? '削除中...'
            : `選択した課題を削除 (${selectedCount})`}
        </button>
      </div>

      <div
        style={{
          overflowX: 'auto',
          border: '1px solid #ddd',
          borderRadius: '8px',
        }}
      >
        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontSize: '0.9rem',
          }}
        >
          <thead>
            <tr
              style={{
                backgroundColor: '#f8f9fa',
                textAlign: 'left',
              }}
            >
              <th style={{ padding: '0.5rem', width: 40 }}>
                <input
                  type="checkbox"
                  onChange={toggleSelectAll}
                  checked={
                    sortedTasks.length > 0 &&
                    sortedTasks.every((t) => selectedIds.includes(t.id))
                  }
                />
              </th>
              <th style={{ padding: '0.5rem', minWidth: 140 }}>タイトル</th>
              <th style={{ padding: '0.5rem', width: 120 }}>期限</th>
              <th style={{ padding: '0.5rem', width: 80 }}>進捗</th>
              <th style={{ padding: '0.5rem', minWidth: 160 }}>内容</th>
              <th style={{ padding: '0.5rem', width: 80 }}>通知</th>
            </tr>
          </thead>
          <tbody>
            {sortedTasks.map((task) => {
              const local = localStates[task.id] ?? {};
              const effectiveIsDone =
                local.is_done !== undefined ? local.is_done : task.is_done;

              // 通知 ON/OFF は親からの共有状態 + task の should_notify / is_done で決定
              const baseNotify =
                (task as any).should_notify !== undefined
                  ? (task as any).should_notify
                  : !task.is_done;
              const override = notifyOverrides[task.id];
              const effectiveNotify =
                override !== undefined ? override : baseNotify;

              const effectiveTitle = local.title ?? task.title;
              const baseMemo = task.memo || task.course_name || '';
              const effectiveMemo = local.memo ?? baseMemo;

              const isSelected = selectedIds.includes(task.id);

              return (
                <tr
                  key={task.id}
                  style={{
                    backgroundColor: isSelected ? '#e9f5ff' : 'white',
                    borderTop: '1px solid #eee',
                  }}
                >
                  <td style={{ padding: '0.5rem', textAlign: 'center' }}>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleSelect(task)}
                    />
                  </td>

                  <td style={{ padding: '0.5rem' }}>
                    <EditableTextCell
                      value={effectiveTitle}
                      placeholder="タイトル"
                      onSave={(v) => handleTitleSave(task, v)}
                    />
                  </td>

                  <td style={{ padding: '0.5rem', whiteSpace: 'nowrap' }}>
                    {formatDeadline(task.deadline)}
                  </td>

                  <td style={{ padding: '0.5rem' }}>
                    <select
                      value={effectiveIsDone ? 'done' : 'todo'}
                      onChange={(e) =>
                        handleToggleDone(task, e.target.value === 'done')
                      }
                      style={{
                        padding: '0.2rem 0.4rem',
                        fontSize: '0.85rem',
                        borderRadius: '4px',
                        border: '1px solid #ccc',
                      }}
                    >
                      <option value="todo">未</option>
                      <option value="done">完</option>
                    </select>
                  </td>

                  <td style={{ padding: '0.5rem', maxWidth: 260 }}>
                    <EditableTextCell
                      value={effectiveMemo}
                      placeholder="内容"
                      onSave={(v) => handleMemoSave(task, v)}
                    />
                  </td>

                  <td style={{ padding: '0.5rem' }}>
                    <NotificationPill
                      isOn={effectiveNotify}
                      onToggle={() =>
                        onNotifyChange(task.id, !effectiveNotify)
                      }
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ここより下はそのまま（ProgressGauge / EditableTextCell / NotificationPill）は元コードと同じ
// ...（質問に貼ってくれた TodayTaskList.tsx の残りをそのまま使ってOK）

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

interface EditableTextCellProps {
  value: string;
  placeholder?: string;
  onSave: (value: string) => void;
}

const EditableTextCell: React.FC<EditableTextCellProps> = ({
  value,
  placeholder,
  onSave,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  const handleClick = () => {
    setDraft(value);
    setIsEditing(true);
  };

  const finish = (commit: boolean) => {
    if (commit && draft !== value) {
      onSave(draft);
    }
    setIsEditing(false);
  };

  if (!isEditing) {
    const displayText = value ? value.split('\n')[0] : '';

    return (
      <div
        onClick={handleClick}
        style={{
          width: '100%',
          minHeight: 24,
          padding: '2px 4px',
          borderRadius: 8,
          cursor: 'text',
          display: 'flex',
          alignItems: 'center',
        }}
      >
        {displayText ? (
          <span
            style={{
              display: 'inline-block',
              maxWidth: '100%',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {displayText}
          </span>
        ) : (
          <span style={{ color: '#9ca3af' }}>{placeholder}</span>
        )}
      </div>
    );
  }

  const lineCount = Math.max(2, draft.split('\n').length);

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        minHeight: 24,
      }}
    >
      <textarea
        autoFocus
        value={draft}
        placeholder={placeholder}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => finish(true)}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
            finish(true);
          } else if (e.key === 'Escape') {
            finish(false);
          }
        }}
        rows={lineCount}
        style={{
          position: 'absolute',
          top: -4,
          left: -4,
          zIndex: 20,
          fontSize: '0.9rem',
          padding: '8px 10px',
          borderRadius: 12,
          border: '1px solid #d1d5db',
          outline: 'none',
          backgroundColor: '#fff',
          boxShadow: '0 12px 32px rgba(15,23,42,0.18)',
          resize: 'vertical',
          whiteSpace: 'pre-wrap',
          lineHeight: 1.4,
          width: 'min(320px, 80vw)',
        }}
      />
    </div>
  );
};

const NotificationPill: React.FC<{
  isOn: boolean;
  onToggle?: () => void;
}> = ({ isOn, onToggle }) => {
  return (
    <div
      onClick={() => onToggle?.()}
      style={{
        width: 40,
        height: 20,
        borderRadius: 9999,
        padding: 2,
        backgroundColor: isOn ? '#22c55e' : '#d1d5db',
        display: 'flex',
        alignItems: 'center',
        justifyContent: isOn ? 'flex-end' : 'flex-start',
        cursor: 'pointer',
        transition: 'background-color 0.15s, justify-content 0.15s',
      }}
    >
      <div
        style={{
          width: 16,
          height: 16,
          borderRadius: '9999px',
          backgroundColor: '#fff',
          boxShadow: '0 0 2px rgba(0,0,0,0.3)',
        }}
      />
    </div>
  );
};
