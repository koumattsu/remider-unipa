// frontend/src/components/TaskList.tsx

import { useState } from 'react';
import { Task, TaskUpdate } from '../types';
import { tasksApi } from '../api/tasks';

interface TaskListProps {
  tasks: Task[];
  onTaskUpdated: () => void;
  notifyOverrides: Record<number, boolean>;
  onNotifyChange: (taskId: number, value: boolean) => void;
  onVirtualTaskDelete?: (taskId: Task) => void;
}

// Task.id が負の値のものは「毎週タスク」からフロント側で生成した仮想タスク
const isVirtualTask = (task: Task) => task.id < 0;

export const TaskList: React.FC<TaskListProps> = ({
  tasks,
  onTaskUpdated,
  notifyOverrides,
  onNotifyChange,
  onVirtualTaskDelete,
}) => {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);



    // ★ 仮タスク用の is_done 上書き状態（フロント限定）
    const [localDoneOverrides, setLocalDoneOverrides] = useState<
      Record<number, boolean>
    >({});

    const handleToggleDone = async (task: Task, newIsDone: boolean) => {
      // ★ 仮タスク（id < 0）はフロントだけで is_done を反映
      if (isVirtualTask(task)) {
        setLocalDoneOverrides((prev) => ({ ...prev, [task.id]: newIsDone }));

        // 仮タスクは「とりあえず今まで通り」進捗と通知を軽く連動させておく
        const hasOverride = notifyOverrides[task.id] !== undefined;
        if (!hasOverride) {
          onNotifyChange(task.id, !newIsDone);
        }
        return;
      }

      // ------- ここから実タスク（API あり） -------
      const payload: TaskUpdate = {
        is_done: newIsDone,
      };

      // ★ いったん「進捗に応じて should_notify を自動でいじる」のはやめる
      //    通知は通知トグル（NotificationPill）を押したときだけ変更することにする

      try {
        await tasksApi.update(task.id, payload);
        onTaskUpdated();
      } catch (error) {
        console.error('課題の更新に失敗しました:', error);
        alert('課題の更新に失敗しました');
      }
    };




  const handleToggleNotify = async (task: Task, newValue: boolean) => {
    // 仮想タスクはフロント側の override だけ
    if (isVirtualTask(task)) {
      onNotifyChange(task.id, newValue);
      return;
    }

    try {
      await tasksApi.update(task.id, { should_notify: newValue });
      onNotifyChange(task.id, newValue);
    } catch (error) {
      console.error('通知設定の更新に失敗しました:', error);
      alert('通知設定の更新に失敗しました');
    }
  };



  


  const handleBulkDelete = async () => {
    const realIds = selectedIds.filter((id) => id > 0);
    const virtualIds = selectedIds.filter((id) => id < 0);

    if (realIds.length === 0 && virtualIds.length === 0) return;

    const totalCount = realIds.length + virtualIds.length;
    if (!confirm(`${totalCount}件の課題をまとめて削除しますか？`)) return;

    try {
      setIsBulkDeleting(true);

      // 実タスクはAPI削除
      if (realIds.length > 0) {
        await Promise.all(realIds.map((id) => tasksApi.delete(id)));
        onTaskUpdated();
      }

      // 仮想タスクは Dashboard に「この週だけ削除」を伝える
      if (virtualIds.length > 0 && onVirtualTaskDelete) {
        const virtualTasks = tasks.filter(t => virtualIds.includes(t.id));
        virtualTasks.forEach(t => onVirtualTaskDelete(t));
      }


      setSelectedIds([]);
    } catch (error) {
      console.error('課題の一括削除に失敗しました:', error);
      alert('課題の一括削除に失敗しました');
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
    if (tasks.length === 0) {
      setSelectedIds([]);
      return;
    }
    const allSelected = tasks.every((t) => selectedIds.includes(t.id));
    if (allSelected) {
      setSelectedIds([]);
    } else {
      setSelectedIds(tasks.map((t) => t.id));
    }
  };
  const formatDeadline = (dateString: string) => {
    const date = new Date(dateString);
    const hours = date.getHours();
    const minutes = date.getMinutes();
 
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

  if (tasks.length === 0) {
    return <p style={{ color: '#666' }}>課題がありません</p>;
  }

  const sortedTasks = [...tasks].sort(
    (a, b) => new Date(a.deadline).getTime() - new Date(b.deadline).getTime()
  );


  // ★ 実タスク/仮想タスクどちらも選択数にカウント
  const selectedCount = selectedIds.length;
  
  return (
    <div>
      {/* 上の「全タスク一覧」のラベルは削除 */}
      <div
        style={{
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
              const isSelected = selectedIds.includes(task.id);

              // ★ 仮タスクは localDoneOverrides を優先して表示
              const overrideDone = localDoneOverrides[task.id];
              const isDone =
                overrideDone !== undefined ? overrideDone : task.is_done;

              // DB に should_notify が入っているか
              const hasNotifyFlag =
                task.should_notify !== undefined && task.should_notify !== null;

              // フラグがあればそれを使う。なければ「未ならON / 完ならOFF」という初期ルール
              const baseNotify = hasNotifyFlag ? !!task.should_notify : !isDone;

              // 親からの override があればそれを優先
              const override = notifyOverrides[task.id];
              const effectiveNotify =
                override !== undefined ? override : baseNotify;

              const baseMemo = task.memo || task.course_name || '';

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
                      value={task.title}
                      placeholder="タイトル"
                      onSave={async (v) => {
                        const trimmed = v.trim();
                        if (!trimmed || trimmed === task.title) return;
                        try {
                          await tasksApi.update(task.id, { title: trimmed });
                          onTaskUpdated();
                        } catch (e) {
                          alert('タイトルの更新に失敗しました');
                        }
                      }}
                    />
                  </td>
                  <td style={{ padding: '0.5rem', whiteSpace: 'nowrap' }}>
                    {formatDeadline(task.deadline)}
                  </td>
                  <td style={{ padding: '0.5rem' }}>
                    <select
                      value={isDone ? 'done' : 'todo'}
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
                      value={baseMemo}
                      placeholder="内容"
                      onSave={async (v) => {
                        const trimmed = v.trim();
                        if (trimmed === baseMemo) return;
                        try {
                          await tasksApi.update(task.id, { memo: trimmed });
                          onTaskUpdated();
                        } catch (e) {
                          alert('内容の更新に失敗しました');
                        }
                      }}
                    />
                  </td>
                  <td style={{ padding: '0.5rem' }}>
                    <NotificationPill
                      isOn={effectiveNotify}
                      onToggle={() => handleToggleNotify(task, !effectiveNotify)}
/>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p style={{ marginTop: '0.75rem', fontSize: '0.85rem', color: '#6b7280' }}>
        ※「毎週タスク」はテンプレートから自動生成されます。授業がない週など、この週だけ削除したい場合は左端で選択して「選択した課題を削除」を押してください。
      </p>
    </div>
  );
};

interface EditableTextCellProps {
  value: string;
  placeholder?: string;
  onSave: (value: string) => void;
}

// ※ EditableTextCell / NotificationPill は TodayTaskList と同じ実装でOK
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

  const displayText = value ? value.split('\n')[0] : '';

  const lineCount = Math.max(2, draft.split('\n').length);

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
      }}
    >
      {/* 表示用レイヤー */}
      <div
        onClick={!isEditing ? handleClick : undefined}
        style={{
          width: '100%',
          minHeight: 24,
          padding: '2px 4px',
          borderRadius: 8,
          cursor: isEditing ? 'default' : 'text',
          display: 'flex',
          alignItems: 'center',
        }}
      >
        {displayText ? (
          <span
            style={{
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

      {/* 編集用オーバーレイ（少し下寄せ） */}
      {isEditing && (
        <div
          style={{
            position: 'absolute',
            top: '60%',
            left: 0,
            transform: 'translateY(-50%)',
            zIndex: 20,
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
              width: 'min(320px, 80vw)',
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
            }}
          />
        </div>
      )}
    </div>
  );
};

const NotificationPill: React.FC<{
  isOn: boolean;
  onToggle?: () => void;
}> = ({ isOn, onToggle }) => (
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
