// frontend/src/components/TaskList.tsx

import { useState, useEffect } from 'react';
import { Task, TaskUpdate} from '../types';
import { tasksApi } from '../api/tasks';
import { taskNotificationOverrideApi } from '../api/taskNotificationOverride';

// Task.id が負の値のものは「毎週タスク」からフロント側で生成した仮想タスク
const isVirtualTask = (task: Task) => task.id < 0;

interface TaskListProps {
  tasks: Task[];
  onTaskUpdated: () => void;
  notifyOverrides?: Record<number, boolean>;
  onNotifyChange?: (taskId: number, value: boolean) => void;
  taskNotificationOverrides?: Record<number, TaskNotificationOptions>;
  onTaskNotificationOptionsChange?: (
    taskId: number,
    value: TaskNotificationOptions
  ) => void;
}

interface TaskNotificationOptions {
  morning: boolean;
  offsetsHours: number[];
}

// モーダル編集中だけで使うドラフト用
type TaskNotificationDraft = {
  morning: boolean;
  offsetsHours: string[]; // 文字列で持つ（編集しやすくするため）
};

// 全タスク共通のデフォルト（バックエンドのデフォルト想定: 朝 + 3時間前）
const DEFAULT_TASK_NOTIFICATION_OPTIONS: TaskNotificationOptions = {
  morning: true,
  offsetsHours: [3],
};

// 🔔 NotificationSettings.tsx で使っている localStorage のキーと揃える
const NOTIFICATION_STORAGE_KEY = 'unipa_notification_settings_v1';

type StoredNotificationSettings = {
  enableMorning: boolean;
  dailyDigestTime: string;
  reminderOffsetsHours: number[];
};
// グローバル通知設定(localStorage) からタスクのデフォルト通知設定を生成
const loadGlobalNotificationDefaults = (): TaskNotificationOptions => {
  if (typeof window === 'undefined') {
    return DEFAULT_TASK_NOTIFICATION_OPTIONS;
  }

  try {
    const raw = window.localStorage.getItem(NOTIFICATION_STORAGE_KEY);
    if (!raw) return DEFAULT_TASK_NOTIFICATION_OPTIONS;

    const parsed = JSON.parse(raw) as StoredNotificationSettings;

    const uniqueOffsets = Array.from(
      new Set(
        (parsed.reminderOffsetsHours ?? [])
          .map((n) => Number(n))
          .filter((n) => Number.isFinite(n) && n > 0)
      )
    );

    return {
      morning:
        parsed.enableMorning !== undefined ? parsed.enableMorning : true,
      offsetsHours: uniqueOffsets.length > 0 ? uniqueOffsets : [3],
    };
  } catch (e) {
    console.warn('通知のグローバル設定読み込みに失敗しました', e);
    return DEFAULT_TASK_NOTIFICATION_OPTIONS;
  }
};

export const TaskList: React.FC<TaskListProps> = ({
  tasks,
  onTaskUpdated,
  notifyOverrides,
  onNotifyChange,
  taskNotificationOverrides,
  onTaskNotificationOptionsChange,
}) => {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);

  // 🔔 タスク個別の通知設定（フロント限定で保持）
  const [localTaskNotificationOverrides, setLocalTaskNotificationOverrides] =
  useState<Record<number, TaskNotificationOptions>>({});

  // 親から来ていればそっちを優先、それがなければローカルstate
const getTaskNotificationOptions = (
  taskId: number
): TaskNotificationOptions | undefined => {
  return (
    taskNotificationOverrides?.[taskId] ??
    localTaskNotificationOverrides[taskId]
  );
};

const saveTaskNotificationOptions = (
  taskId: number,
  opts: TaskNotificationOptions
) => {
  if (onTaskNotificationOptionsChange) {
    onTaskNotificationOptionsChange(taskId, opts);
  } else {
    setLocalTaskNotificationOverrides((prev) => ({
      ...prev,
      [taskId]: opts,
    }));
  }
};


  // ✏️ タイトル・締切編集用
  const [editingTaskId, setEditingTaskId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState('');
  
  // 日付＋時刻（24時対応）
  const [editDate, setEditDate] = useState('');      // yyyy-MM-dd
  const [editHour, setEditHour] = useState('24');    // '01'〜'24'
  const [editMinute, setEditMinute] = useState('00'); // '00' or '30'

  // スマホ判定
  const [isMobile, setIsMobile] = useState(false);

  // ギアメニューをどのタスクに対して開いているか
  const [menuTaskId, setMenuTaskId] = useState<number | null>(null);

  // 🔔 通知設定モーダルの対象タスク
  const [notificationModalTask, setNotificationModalTask] = useState<Task | null>(null);
  const [notificationDraft, setNotificationDraft] =
    useState<TaskNotificationDraft | null>(null);

  const handleNotificationOffsetChange = (index: number, value: string) => {
    setNotificationDraft((prev) => {
      if (!prev) return prev;

      // 半角数字以外を全部削除（全角も消える）
      const onlyDigits = value.replace(/[^0-9]/g, '');

      const offsets = [...prev.offsetsHours];
      offsets[index] = onlyDigits;

      return { ...prev, offsetsHours: offsets };
    });
  };


  const handleNotificationOffsetRemove = (index: number) => {
    setNotificationDraft((prev) => {
      if (!prev) return prev;
      const offsets = prev.offsetsHours.filter((_, i) => i !== index);
      return {
        ...prev,
        offsetsHours: offsets.length ? offsets : ['1'], // 最低1個は残す
      };
    });
  };

  const handleNotificationOffsetAdd = () => {
    setNotificationDraft((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        offsetsHours: [...prev.offsetsHours, '1'],
      };
    });
  };



  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia('(max-width: 768px)');
    const update = () => setIsMobile(mq.matches);
    update();
    mq.addEventListener('change', update);
    return () => mq.removeEventListener('change', update);
  }, []);

  // 🔔 通知設定モーダルを開く
  const openNotificationModal = (task: Task) => {
    setNotificationModalTask(task);

    const existing = getTaskNotificationOptions(task.id);
    if (existing) {
      // 既存の設定 → 文字列に変換
      setNotificationDraft({
        morning: existing.morning,
        offsetsHours: existing.offsetsHours.map((n) => String(n)),
      });
    } else {
      // グローバル設定から初期値生成
      const defaults = loadGlobalNotificationDefaults();
      setNotificationDraft({
        morning: defaults.morning,
        offsetsHours: defaults.offsetsHours.map((n) => String(n)),
      });
    }
  };


  const closeNotificationModal = () => {
    setNotificationModalTask(null);
    setNotificationDraft(null);
  };

  const handleToggleDone = async (task: Task, newIsDone: boolean) => {
    try {
      await tasksApi.update(task.id, {
        is_done: newIsDone,
        // ✅ should_notify は送らない（通知のON/OFFはバック側ロジック or 通知トグルだけ）
      });
      onTaskUpdated();
    } catch (error) {
      console.error('課題の更新に失敗しました:', error);
      alert('課題の更新に失敗しました');
    }
  };

  const handleToggleNotify = async (task: Task, newValue: boolean) => {
    // 仮想タスク(id<0) → 親に委譲（localStorage更新）
    if (isVirtualTask(task)) {
      onNotifyChange?.(task.id, newValue);
      return;
    }

    // 実タスク(id>0) → DB更新
    try {
      await tasksApi.update(task.id, { should_notify: newValue });
      onTaskUpdated();
    } catch (error) {
      console.error('通知設定の更新に失敗しました:', error);
      alert('通知設定の更新に失敗しました');
    }
  };

  const handleBulkDelete = async () => {
    const realIds = selectedIds.filter((id) => id > 0);
    if (realIds.length === 0) return;

    if (!confirm(`${realIds.length}件の課題をまとめて削除しますか？`)) return;

    try {
      setIsBulkDeleting(true);
      await Promise.all(realIds.map((id) => tasksApi.delete(id)));
      setSelectedIds([]);
      onTaskUpdated();
    } catch (error) {
      console.error('課題の一括削除に失敗しました:', error);
      alert('課題の一括削除に失敗しました');
    } finally {
      setIsBulkDeleting(false);
    }
  };

  const toggleSelect = (task: Task) => {
    setSelectedIds((prev) =>
      prev.includes(task.id)
        ? prev.filter((id) => id !== task.id)
        : [...prev, task.id]
    );
  };

  const toggleSelectAll = () => {
    if (tasks.length === 0) {
      setSelectedIds([]);
      return;
    }
    const allSelected = tasks.every((t) => selectedIds.includes(t.id));
    setSelectedIds(allSelected ? [] : tasks.map((t) => t.id));
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
    return (
      <div
        className="glass"
        style={{
          borderRadius: 18,
          padding: '1.1rem 1rem',
          textAlign: 'center',
        }}
      >
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: 9999,
            margin: '0 auto 0.6rem',
            background:
              'radial-gradient(circle at 30% 30%, rgba(91,231,255,.35), rgba(255,255,255,.06))',
            border: '1px solid rgba(255,255,255,.12)',
            boxShadow: '0 10px 30px rgba(0,0,0,.35)',
          }}
        />
        <div style={{ fontWeight: 700, letterSpacing: '0.02em' }}>
          今日の課題はゼロ
        </div>
        <div style={{ marginTop: 6, fontSize: '0.85rem', color: 'var(--muted)' }}>
          追加するか、週次タスクを materialize してみよう
        </div>
      </div>
    );
  }

  // ✅ TaskList.tsx の buildDeadlineFromParts をこれにする（最小）
  const buildDeadlineFromParts = (
    dateStr: string,
    hourStr: string,
    minuteStr: string
  ): string | null => {
    if (!dateStr || !hourStr || !minuteStr) return null;

    const [year, month, day] = dateStr.split('-').map(Number);
    let hourNum = Number(hourStr);
    const minuteNum = Number(minuteStr);

    if (!year || !month || !day || Number.isNaN(hourNum) || Number.isNaN(minuteNum)) {
      return null;
    }

    // ローカル（JST）として Date を作る
    const base = new Date(year, month - 1, day, 0, 0, 0, 0);

    // 24:00 は翌日 00:00
    if (hourNum === 24) {
      base.setDate(base.getDate() + 1);
      hourNum = 0;
    }

    base.setHours(hourNum, minuteNum, 0, 0);

    // ✅ サーバーへはUTC確定文字列で送る（Z付き）
    return base.toISOString();
  };


  const sortedTasks = [...tasks].sort(
    (a, b) => new Date(a.deadline).getTime() - new Date(b.deadline).getTime()
  );

  const selectedCount = selectedIds.length;

    // 共通: 編集モーダルを開く
  const openEditModal = (task: Task) => {
    const d = new Date(task.deadline);
    let baseDate = new Date(d);
    let hour = d.getHours();
    const minute = d.getMinutes();

    if (hour === 0 && minute === 0) {
      baseDate.setDate(baseDate.getDate() - 1);
      hour = 24;
    }

    const pad = (n: number) => String(n).padStart(2, '0');
    const yyyy = baseDate.getFullYear();
    const mm = pad(baseDate.getMonth() + 1);
    const dd = pad(baseDate.getDate());

    setEditingTaskId(task.id);
    setEditTitle(task.title || '');
    setEditDate(`${yyyy}-${mm}-${dd}`);
    setEditHour(pad(hour));
    setEditMinute(pad(minute));
  };

  return (
    <div>
      {/* 上部：一括削除ボタン */}
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

      {/* PC / タブレット向け: テーブル表示 */}
      {!isMobile && (
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

                const isDone = Boolean(task.is_done);

                const effectiveNotify = isVirtualTask(task)
                  ? (notifyOverrides?.[task.id] ?? true) // 仮想はlocalStorage(親状態)
                  : Boolean(task.should_notify);          // 実タスクはDB

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
                          } catch {
                            alert('タイトルの更新に失敗しました');
                          }
                        }}
                      />
                    </td>
                    <td style={{ padding: '0.5rem', whiteSpace: 'nowrap' }}>
                      <div
                        style={{
                          position: 'relative',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: 4,
                        }}
                      >
                        <span>{formatDeadline(task.deadline)}</span>

                        {/* ⚙️ アイコンは仮タスクも含めて全タスクに表示 */}
                        <button
                          type="button"
                          onClick={() =>
                            setMenuTaskId(menuTaskId === task.id ? null : task.id)
                          }
                          aria-label="タスクのメニューを開く"
                          style={{
                            border: 'none',
                            background: 'transparent',
                            cursor: 'pointer',
                            padding: 2,
                            fontSize: '1.1rem',
                          }}
                        >
                          ⚙️
                        </button>

                        {/* ギアメニュー */}
                        {menuTaskId === task.id && (
                          <div
                            className="glass-strong"
                            style={{
                              position: 'absolute',
                              top: '110%',
                              right: 0,
                              minWidth: 120,
                              borderRadius: 10,
                              boxShadow: '0 12px 30px rgba(0,0,0,0.35)',
                              zIndex: 40,
                              overflow: 'hidden',
                            }}
                          >
                            {/* 実タスク / 仮タスク 共通で「編集」 */}
                            <button
                              type="button"
                              onClick={() => {
                                openEditModal(task);
                                setMenuTaskId(null);
                              }}
                              style={{
                                width: '100%',
                                padding: '0.5rem 0.8rem',
                                fontSize: '0.85rem',
                                textAlign: 'left',
                                border: 'none',
                                background: 'transparent',
                                color: 'rgba(255,255,255,.9)',
                                cursor: 'pointer',
                              }}
                            >
                              編集
                            </button>

                            {/* 「通知」はそのまま */}
                            <button
                              type="button"
                              onClick={() => {
                                openNotificationModal(task);
                                setMenuTaskId(null);
                              }}
                              style={{
                                width: '100%',
                                padding: '0.5rem 0.8rem',
                                fontSize: '0.85rem',
                                textAlign: 'left',
                                borderTop: '1px solid rgba(255,255,255,.12)',
                                borderBottom: 'none',
                                borderLeft: 'none',
                                borderRight: 'none',
                                background: 'white',
                                cursor: 'pointer',
                              }}
                            >
                              通知
                            </button>
                          </div>
                        )}
                      </div>
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
                          } catch {
                            alert('内容の更新に失敗しました');
                          }
                        }}
                      />
                    </td>
                    <td style={{ padding: '0.5rem' }}>
                      <NotificationPill
                        isOn={effectiveNotify}
                        onToggle={() =>
                          handleToggleNotify(task, !effectiveNotify)
                        }
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* スマホ向け: 1タスク = 1カード */}
      {isMobile && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '0.75rem',
          }}
        >
          {sortedTasks.map((task) => {
            const isSelected = selectedIds.includes(task.id);

            const isDone = Boolean(task.is_done);

            const effectiveNotify = isVirtualTask(task)
              ? (notifyOverrides?.[task.id] ?? true)
              : Boolean(task.should_notify);

            const baseMemo = task.memo || task.course_name || '';

            return (
              <div
                key={task.id}
                style={{
                  borderRadius: 18,
                  padding: '0.85rem 0.95rem',
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(255,255,255,0.10)',
                  backdropFilter: 'blur(16px)',
                  WebkitBackdropFilter: 'blur(16px)',
                  boxShadow: '0 16px 44px rgba(0,0,0,0.45)',
                }}
              >
                {/* 1行目: チェックボックス + タイトル + ✏️ */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '0.4rem',
                    marginBottom: '0.35rem',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                      flex: 1,
                      minWidth: 0,
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleSelect(task)}
                      style={{ flexShrink: 0 }}
                    />
                    <div
                      style={{
                        fontWeight: 600,
                        fontSize: '1rem',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {task.title || 'タイトル未設定'}
                    </div>
                  </div>

                  {/* ★ ここは isVirtualTask に関係なく常にラッパーを描画 */}
                  <div style={{ position: 'relative' }}>
                    <button
                      type="button"
                      onClick={() =>
                        setMenuTaskId(menuTaskId === task.id ? null : task.id)
                      }
                      aria-label="タスクのメニューを開く"
                      style={{
                        border: 'none',
                        background: 'transparent',
                        cursor: 'pointer',
                        padding: 4,
                        borderRadius: 9999,
                        fontSize: '1.1rem',
                        flexShrink: 0,
                      }}
                    >
                      ⚙️
                    </button>

                    {menuTaskId === task.id && (
                      <div
                        style={{
                          position: 'absolute',
                          top: '110%',
                          right: 0,
                          minWidth: 120,
                          borderRadius: 10,
                          backgroundColor: '#ffffff',
                          boxShadow: '0 12px 30px rgba(15,23,42,0.28)',
                          border: '1px solid #e5e7eb',
                          zIndex: 40,
                          overflow: 'hidden',
                        }}
                      >
                        {/* 実タスク / 仮タスク 共通で「編集」 */}
                        <button
                          type="button"
                          onClick={() => {
                            openEditModal(task);
                            setMenuTaskId(null);
                          }}
                          style={{
                            width: '100%',
                            padding: '0.5rem 0.8rem',
                            fontSize: '0.85rem',
                            textAlign: 'left',
                            border: 'none',
                            background: 'white',
                            cursor: 'pointer',
                          }}
                        >
                          編集
                        </button>

                        {/* 「通知」はそのまま */}
                        <button
                          type="button"
                          onClick={() => {
                            openNotificationModal(task);
                            setMenuTaskId(null);
                          }}
                          style={{
                            width: '100%',
                            padding: '0.5rem 0.8rem',
                            fontSize: '0.85rem',
                            textAlign: 'left',
                            borderTop: '1px solid #e5e7eb',
                            borderBottom: 'none',
                            borderLeft: 'none',
                            borderRight: 'none',
                            background: 'white',
                            cursor: 'pointer',
                          }}
                        >
                          通知
                        </button>
                      </div>
                    )}
                  </div>

                </div>

                {/* 2行目: 期限 */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    fontSize: '0.8rem',
                    color: 'rgba(255,255,255,.62)',
                    marginBottom: '0.4rem',
                  }}
                >
                  <span style={{ marginRight: '0.35rem' }}>🕒</span>
                  <span>{formatDeadline(task.deadline)}</span>
                </div>

                {/* 3行目: 進捗 + 通知 */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '0.5rem',
                    marginBottom: '0.4rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span
                      style={{
                        fontSize: '0.8rem',
                        color: 'rgba(255,255,255,.62)',
                        marginRight: 4,
                      }}
                    >
                      進捗
                    </span>
                    <select
                      value={isDone ? 'done' : 'todo'}
                      onChange={(e) =>
                        handleToggleDone(task, e.target.value === 'done')
                      }
                      style={{
                        padding: '0.2rem 0.5rem',
                        fontSize: '0.8rem',
                        borderRadius: 9999,
                        border: '1px solid rgba(255,255,255,.12)',
                        background: 'rgba(255,255,255,.06)',
                        color: 'rgba(255,255,255,.92)',
                      }}
                    >
                      <option value="todo">未</option>
                      <option value="done">完</option>
                    </select>
                  </div>

                  <div
                    style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                  >
                    <span
                      style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,.62)' }}
                    >
                      通知
                    </span>
                    <NotificationPill
                      isOn={effectiveNotify}
                      onToggle={() =>
                        handleToggleNotify(task, !effectiveNotify)
                      }
                    />
                  </div>
                </div>

                {/* 4行目: 内容 */}
                <div>
                  <div
                    style={{
                      fontSize: '0.8rem',
                      color: 'rgba(255,255,255,.62)',
                      marginBottom: 2,
                    }}
                  >
                    内容
                  </div>
                  <EditableTextCell
                    value={baseMemo}
                    placeholder="内容"
                    onSave={async (v) => {
                      const trimmed = v.trim();
                      if (trimmed === baseMemo) return;
                      try {
                        await tasksApi.update(task.id, { memo: trimmed });
                        onTaskUpdated();
                      } catch {
                        alert('内容の更新に失敗しました');
                      }
                    }}
                  />
                </div>

                {/* ✏️ 編集フォーム */}
                
              </div>
            );
          })}
        </div>
      )}

    {/* 編集モーダル（カードのサイズを変えずに編集できるようにする） */}
      {editingTaskId !== null && (() => {
        const t = tasks.find((task) => task.id === editingTaskId);
        if (!t) return null;

        return (
          <div
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(15,23,42,0.35)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 50,
            }}
          >
            <div
              className="glass-strong"
              style={{
                width: 'min(480px, 92vw)',
                borderRadius: 24,
                padding: '1.2rem 1rem 1rem',
                boxShadow: '0 16px 44px rgba(0,0,0,0.45)',
              }}
            >
              <div
                style={{
                  fontSize: '0.9rem',
                  fontWeight: 600,
                  marginBottom: '0.75rem',
                  color: 'rgba(255,255,255,.92)',
                }}
              >
                タスク詳細を編集
              </div>

              <label
                style={{
                  fontSize: '0.85rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.25rem',
                  marginBottom: '0.75rem',
                }}
              >
                タイトル
                <input
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  style={{
                    padding: '0.5rem 0.9rem',
                    borderRadius: 9999,
                    fontSize: '0.9rem',
                    color: 'rgba(255,255,255,.92)',
                    background: 'rgba(255,255,255,.06)',
                    border: '1px solid rgba(255,255,255,.12)',
                  }}
                />
              </label>

              <label
                style={{
                  fontSize: '0.85rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.35rem',
                  marginBottom: '0.9rem',
                }}
              >
                締切
                <div
                  style={{
                    display: 'flex',
                    gap: '0.5rem',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                  }}
                >
                  {/* 日付 */}
                  <input
                    type="date"
                    value={editDate}
                    onChange={(e) => setEditDate(e.target.value)}
                    style={{
                      padding: '0.45rem 0.7rem',
                      borderRadius: 9999,
                      fontSize: '0.9rem',
                      color: 'rgba(255,255,255,.92)',
                      background: 'rgba(255,255,255,.06)',
                      border: '1px solid rgba(255,255,255,.12)',
                    }}
                  />

                  {/* 時刻（1〜24時, 0時なし / 24:00あり） */}
                  <select
                    value={editHour}
                    onChange={(e) => setEditHour(e.target.value)}
                    style={{
                      padding: '0.45rem 0.7rem',
                      borderRadius: 9999,
                      fontSize: '0.9rem',
                      color: 'rgba(255,255,255,.92)',
                      background: 'rgba(255,255,255,.06)',
                      border: '1px solid rgba(255,255,255,.12)',
                    }}
                  >
                    {Array.from({ length: 23 }, (_, i) => {
                      const h = i + 1; // 1〜23
                      const label = `${String(h).padStart(2, '0')}:00`;
                      const value = String(h).padStart(2, '0');
                      return (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      );
                    })}
                    {/* 24:00 */}
                    <option value="24">24:00</option>
                  </select>

                  {/* 分（00 / 30） */}
                  <select
                    value={editMinute}
                    onChange={(e) => setEditMinute(e.target.value)}
                    style={{
                      padding: '0.45rem 0.7rem',
                      borderRadius: 9999,
                      fontSize: '0.9rem',
                      color: 'rgba(255,255,255,.92)',
                      background: 'rgba(255,255,255,.06)',
                      border: '1px solid rgba(255,255,255,.12)',
                    }}
                  >
                    <option value="00">00</option>
                    <option value="30">30</option>
                  </select>
                </div>
              </label>


              <div
                style={{
                  display: 'flex',
                  justifyContent: 'flex-end',
                  gap: '0.5rem',
                }}
              >
                <button
                  type="button"
                  onClick={() => setEditingTaskId(null)}
                  style={{
                    padding: '0.4rem 1rem',
                    borderRadius: 9999,
                    border: '1px solid #cbd5e1',
                    backgroundColor: '#fff',
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                  }}
                >
                  キャンセル
                </button>
                                <button
                  type="button"
                  onClick={async () => {
                    if (!editTitle.trim() || !editDate || !editHour || !editMinute) {
                      alert('タイトルと締切は必須です');
                      return;
                    }

                    const deadlineStr = buildDeadlineFromParts(
                      editDate,
                      editHour,
                      editMinute
                    );

                    if (!deadlineStr) {
                      alert('締切の形式が不正です');
                      return;
                    }

                    try {
                      const payload: TaskUpdate = {
                        title: editTitle.trim(),
                        deadline: deadlineStr,
                      };
                      await tasksApi.update(t.id, payload);

                      setEditingTaskId(null);
                      onTaskUpdated();
                    } catch (e) {
                      console.error('タスクの更新に失敗しました:', e);
                      alert('タスクの更新に失敗しました');
                    }
                  }}


                  style={{
                    padding: '0.4rem 1.1rem',
                    borderRadius: 9999,
                    border: 'none',
                    fontSize: '0.85rem',
                    background: 'linear-gradient(135deg, #22c55e, #16a34a)',
                    color: '#fff',
                    cursor: 'pointer',
                  }}
                >
                  保存
                </button>
              </div>
            </div>
          </div>
        );
      })()}

            {/* 🔔 タスク個別の通知設定モーダル（フロント限定ダミー） */}
      {notificationModalTask && notificationDraft && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15,23,42,0.35)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 60,
          }}
          onClick={closeNotificationModal}
        >
          <div
            className="glass-strong"
            style={{
              width: 'min(460px, 92vw)',
              borderRadius: 24,
              padding: '1.2rem 1rem 1rem',
              boxShadow: '0 16px 44px rgba(0,0,0,0.45)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                fontSize: '0.9rem',
                fontWeight: 600,
                marginBottom: '0.5rem',
                color: 'rgba(255,255,255,.92)',
              }}
            >
              「{notificationModalTask.title || 'タイトル未設定'}」の通知タイミング
            </div>
            <p
              style={{
                fontSize: '0.8rem',
                color: 'rgba(255,255,255,.62)',
                marginBottom: '0.75rem',
                lineHeight: 1.5,
              }}
            >
              このタスクだけ、通知タイミングをカスタマイズできます。
              <br />
              （今はフロント側だけのダミー実装で、リロードするとリセットされます）
            </p>

            {/* 当日朝の通知 ON/OFF */}
            <label
              style={{
                fontSize: '0.85rem',
                display: 'flex',
                gap: 8,
                alignItems: 'center',
                marginBottom: '0.75rem',
              }}
            >
              <input
                type="checkbox"
                checked={notificationDraft.morning}
                onChange={(e) =>
                  setNotificationDraft((prev) =>
                    prev ? { ...prev, morning: e.target.checked } : prev
                  )
                }
              />
              当日朝の通知（例: 8:00）
            </label>

            {/* 締切◯時間前通知（自由入力） */}
            <div style={{ marginBottom: '0.9rem' }}>
              <div
                style={{
                  fontSize: '0.85rem',
                  marginBottom: '0.4rem',
                }}
              >
                締切の◯時間前に通知（このタスク専用）
              
                <p
                  style={{
                    marginTop: '0.4rem',
                    marginBottom: '0.6rem',
                    fontSize: '0.75rem',
                    color: 'rgba(255,255,255,.62)',
                  }}
                >
                  ※ 半角数字のみ入力可
                </p>
              </div>  


              {notificationDraft.offsetsHours.map((offset, index) => (
                <div
                  key={index}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    marginBottom: '0.4rem',
                  }}
                >
                  <input
                    type="text"
                    inputMode="numeric"      // スマホで数字キーボード
                    pattern="[0-9]*"
                    value={offset}
                    onChange={(e) =>
                      handleNotificationOffsetChange(index, e.target.value)
                    }
                    style={{
                      width: '80px',
                      padding: '0.4rem 0.6rem',
                      borderRadius: 9999,
                      color: 'rgba(255,255,255,.92)',
                      background: 'rgba(255,255,255,.06)',
                      border: '1px solid rgba(255,255,255,.12)',
                      fontSize: '0.9rem',
                    }}
                  />
                  <span style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,.82)' }}>時間前</span>
                  <button
                    type="button"
                    onClick={() => handleNotificationOffsetRemove(index)}
                    style={{
                      padding: '0.25rem 0.7rem',
                      borderRadius: 9999,
                      border: 'none',
                      fontSize: '0.8rem',
                      backgroundColor: '#ef4444',
                      color: '#fff',
                      cursor: 'pointer',
                    }}
                  >
                    削除
                  </button>
                </div>
              ))}

              <button
                type="button"
                onClick={handleNotificationOffsetAdd}
                style={{
                  marginTop: '0.25rem',
                  padding: '0.35rem 0.9rem',
                  borderRadius: 9999,
                  border: 'none',
                  fontSize: '0.85rem',
                  backgroundColor: '#3b82f6',
                  color: '#fff',
                  cursor: 'pointer',
                }}
              >
                時間を追加
              </button>
            </div>

            <div
              style={{
                display: 'flex',
                justifyContent: 'flex-end',
                gap: '0.5rem',
              }}
            >
              <button
                type="button"
                onClick={closeNotificationModal}
                style={{
                  padding: '0.4rem 1rem',
                  borderRadius: 9999,
                  border: '1px solid rgba(255,255,255,.14)',
                  background: 'rgba(255,255,255,.06)',
                  color: 'rgba(255,255,255,.90)',
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                }}
              >
                キャンセル
              </button>
              <button
                type="button"
                onClick={async () => {
                  if (!notificationModalTask || !notificationDraft) return;

                  // 文字列 → 数値に変換 & 1以上だけ残す & 重複削除
                  const cleanedOffsets = Array.from(
                    new Set(
                      notificationDraft.offsetsHours
                        .map((s) => Number(s))
                        .filter((n) => Number.isFinite(n) && n > 0)
                    )
                  );

                  const toSave: TaskNotificationOptions = {
                    morning: notificationDraft.morning,
                    offsetsHours: cleanedOffsets.length > 0 ? cleanedOffsets : [1],
                  };

                  try {
                    // 実タスク（id > 0）のときだけ、バックエンドに保存
                    if (notificationModalTask.id > 0) {
                      await taskNotificationOverrideApi.upsert(notificationModalTask.id, {
                        enable_morning: toSave.morning,
                        reminder_offsets_hours: toSave.offsetsHours,
                      });
                    }

                    // フロント state / localStorage も更新
                    saveTaskNotificationOptions(notificationModalTask.id, toSave);

                    closeNotificationModal();
                  } catch (e) {
                    console.error('タスク通知設定の保存に失敗しました:', e);
                    alert('タスク通知設定の保存に失敗しました');
                  }
                }}
                style={{
                  padding: '0.4rem 1.1rem',
                  borderRadius: 9999,
                  border: 'none',
                  fontSize: '0.85rem',
                  background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
                  color: '#fff',
                  cursor: 'pointer',
                }}
              >
                保存
              </button>

            </div>
          </div>
        </div>
      )}



      <p style={{ marginTop: '0.75rem', fontSize: '0.85rem', color: 'rgba(255,255,255,.62)'}}>
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
