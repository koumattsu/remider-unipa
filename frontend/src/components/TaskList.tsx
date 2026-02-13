// frontend/src/components/TaskList.tsx

import { useEffect, useRef, useState } from 'react';
import { Task, TaskUpdate} from '../types';
import { tasksApi } from '../api/tasks';
import { taskNotificationOverrideApi } from '../api/taskNotificationOverride';

// Task.id が負の値のものは「毎週タスク」からフロント側で生成した仮想タスク
const isVirtualTask = (task: Task) => task.id < 0;

interface TaskListProps {
  tasks: Task[];
  onTaskUpdated: () => void;
  onTaskPatched?: (taskId: number, patch: Partial<Task>) => void;
  onTasksRemoved?: (ids: number[]) => void;
  notifyOverrides?: Record<number, boolean>;
  onNotifyChange?: (taskId: number, value: boolean) => void;
  taskNotificationOverrides?: Record<number, TaskNotificationOptions>;
  onTaskNotificationOptionsChange?: (
    taskId: number,
    value: TaskNotificationOptions
  ) => void;
  isOverdueView?: boolean;

  // ✅ 追加：無料/有料のUI分岐用（表示制御のみ）
  isPremium?: boolean;

  // ✅ 追加：無料ユーザーがCTAを押したときの遷移（親に委譲）
  onRequestUpgrade?: () => void;
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
  onTaskPatched,
  onTasksRemoved,
  notifyOverrides,
  onNotifyChange,
  taskNotificationOverrides,
  onTaskNotificationOptionsChange,
  isOverdueView = false,
  isPremium = false,
  onRequestUpgrade,
}) => {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);
  const [justDoneTaskId, setJustDoneTaskId] = useState<number | null>(null);

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
  const [editMemo, setEditMemo] = useState('');
  
  // 日付＋時刻（24時対応）
  const [editDate, setEditDate] = useState('');      // yyyy-MM-dd
  const [editHour, setEditHour] = useState('24');    // '01'〜'24'
  const [editMinute, setEditMinute] = useState('00'); // '00' or '30'

  // ギアメニュー（fixed表示用：位置rectも保持）
  const [menuState, setMenuState] = useState<{
    taskId: number;
    rect: DOMRect;
  } | null>(null);

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
    const prevDone = Boolean(task.is_done);
    const prevNotify = Boolean(task.should_notify);
    const prevAuto = Boolean(task.auto_notify_disabled_by_done);
    // ✅ バックエンド設計と同じ “次の表示” をフロントでも作る（即反映）
    let nextNotify = prevNotify;
    let nextAuto = prevAuto;
    if (newIsDone === true) {
      if (prevNotify === true) {
        nextNotify = false;
        nextAuto = true;  // 完了OFF扱い
      } else {
        nextNotify = false; // 既にOFF（手動OFFの可能性）
        nextAuto = false;  // 完了OFF扱いにしない
      }
    } else {
      // 未完了に戻す：完了OFFだった分だけ復帰
      if (prevAuto === true) {
        nextNotify = true;
        nextAuto = false;
      } else {
        // 手動OFFなら復帰させない
        nextNotify = prevNotify;
        nextAuto = prevAuto;
      }
    }
    const nowIso = new Date().toISOString();

    onTaskPatched?.(task.id, {
      is_done: newIsDone,
      completed_at: newIsDone ? (task.completed_at ?? nowIso) : null,
      should_notify: nextNotify,
      auto_notify_disabled_by_done: nextAuto,
    });

    // ✅ “完了になった瞬間だけ” 演出（reduced motion は CSS 側で無効化）
    if (newIsDone === true) {
      setJustDoneTaskId(task.id);
      window.setTimeout(() => {
        setJustDoneTaskId((prev) => (prev === task.id ? null : prev));
      }, 900);
    } else {
      // 未完に戻したら瞬間演出は消す
      setJustDoneTaskId((prev) => (prev === task.id ? null : prev));
    }

    // 仮タスクはフロントだけで完結（API叩かない）
    if (isVirtualTask(task)) return;
    try {
      await tasksApi.update(task.id, {
        is_done: newIsDone,
        should_notify: nextNotify,
      });
    } catch (error) {
      console.error('課題の更新に失敗しました:', error);
      // rollback（進捗・通知・auto全部戻す）
      onTaskPatched?.(task.id, {
        is_done: prevDone,
        completed_at: task.completed_at ?? null,
        should_notify: prevNotify,
        auto_notify_disabled_by_done: prevAuto,
      });

      // ✅ rollback 時は演出も戻す（事故防止）
      setJustDoneTaskId((prev) => (prev === task.id ? null : prev));

      alert('課題の更新に失敗しました');
    }
  };

  const handleToggleNotify = async (task: Task, newValue: boolean) => {
    // 仮想タスク(id<0) → 親に委譲（localStorage更新）
    if (isVirtualTask(task)) {
      onNotifyChange?.(task.id, newValue);
      return;
    }
    const prev = Boolean(task.should_notify);
    const prevAuto = Boolean(task.auto_notify_disabled_by_done);
    onTaskPatched?.(task.id, { should_notify: newValue, auto_notify_disabled_by_done: false });
    try {
      await tasksApi.update(task.id, { should_notify: newValue });
    } catch (error) {
      console.error('通知設定の更新に失敗しました:', error);
      onTaskPatched?.(task.id, { should_notify: prev, auto_notify_disabled_by_done: prevAuto }); // rollback
      alert('通知設定の更新に失敗しました');
    }
  };

  const handleBulkDelete = async () => {
    const realIds = selectedIds.filter((id) => id > 0);
    if (realIds.length === 0) return;

    if (!confirm(`${realIds.length}件の課題をまとめて削除しますか？`)) return;

    try {
      setIsBulkDeleting(true);
      // 先にローカルから消す（即反映）
      onTasksRemoved?.(realIds);
      await Promise.all(realIds.map((id) => tasksApi.delete(id)));
      setSelectedIds([]);
    } catch (error) {
      console.error('課題の一括削除に失敗しました:', error);
      // 失敗したらサーバーから復元
      onTaskUpdated();
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

  const formatDeadline = (dateString: string) => {
    const date = new Date(dateString);
    const hours = date.getHours();
    const minutes = date.getMinutes();

    // ✅ 0時台は「前日 24:MM」表記に寄せる（24:30 も対応）
    if (hours === 0) {
      const prev = new Date(date);
      prev.setDate(prev.getDate() - 1);

      const month = String(prev.getMonth() + 1).padStart(2, '0');
      const day = String(prev.getDate()).padStart(2, '0');
      const m = String(minutes).padStart(2, '0');
      return `${month}/${day} 24:${m}`;
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

  const selectedCount = selectedIds.length;

    // 共通: 編集モーダルを開く
  
  const openEditModal = (task: Task) => {
    const d = new Date(task.deadline);
    let baseDate = new Date(d);
    let hour = d.getHours();
    const minute = d.getMinutes();

    // ✅ 0時台は「前日 24:MM」に逆変換してモーダルへ入れる
    if (hour === 0) {
      baseDate.setDate(baseDate.getDate() - 1);
      hour = 24;
    }

    const pad = (n: number) => String(n).padStart(2, '0');
    const yyyy = baseDate.getFullYear();
    const mm = pad(baseDate.getMonth() + 1);
    const dd = pad(baseDate.getDate());

    setEditingTaskId(task.id);
    setEditTitle(task.title || '');
    setEditMemo(task.memo ?? '');
    setEditDate(`${yyyy}-${mm}-${dd}`);
    setEditHour(pad(hour));
    setEditMinute(pad(minute));
  };

  return (
    <div>
      <style>{`
        @keyframes doneShimmer {
          0%   { transform: translateX(-35%); opacity: 0.10; }
          50%  { transform: translateX(35%);  opacity: 0.22; }
          100% { transform: translateX(-35%); opacity: 0.10; }
        }

        /* ✅ 完了になった瞬間だけ：ふわっとフェード＆微グロー（うるさくしない） */
        @keyframes doneEnter {
          0%   { opacity: 0.72; transform: translateY(1px); filter: brightness(1) saturate(1); }
          60%  { opacity: 0.92; transform: translateY(0px); filter: brightness(1.06) saturate(1.08); }
          100% { opacity: 0.88; transform: translateY(0px); filter: brightness(1) saturate(1); }
        }

        /* ✅ 未定義だったので追加：超弱い“呼吸”だけ（重くしない） */
        @keyframes doneAura {
          0%, 100% { opacity: 0.18; transform: translate3d(0,0,0) scale(1); }
          50%      { opacity: 0.28; transform: translate3d(0,0,0) scale(1.02); }
        }

        @media (prefers-reduced-motion: reduce) {
          .done-shimmer { animation: none !important; }
          .done-just { animation: none !important; }
          .done-aura { animation: none !important; }
        }
      `}</style>
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

      {/* ✅ 全デバイス共通: 1タスク = 1カード（SSOT） */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: '0.9rem',
          alignItems: 'stretch',
          width: '100%',
          maxWidth: 1100,
          margin: '0 auto',
        }}
      >
        {tasks.map((task) => {
          const isSelected = selectedIds.includes(task.id);

          const isDone = Boolean(task.is_done);
          const isJustDone = isDone && justDoneTaskId === task.id;
          const isOverdueNow = !isDone && new Date(task.deadline).getTime() < Date.now();

          const effectiveNotify = isVirtualTask(task)
            ? (notifyOverrides?.[task.id] ?? true)
            : Boolean(task.should_notify);

          const MANUAL_COURSE_NAME = '__manual__';

          const baseMemo =
            (task.memo && task.memo.trim())
              ? task.memo.trim()
              : (task.course_name && task.course_name !== MANUAL_COURSE_NAME)
                ? task.course_name
                : '';

          const isManual = task.course_name === MANUAL_COURSE_NAME;
          const showContentRow = Boolean(baseMemo) || !isManual;      

          return (
            <div
              key={task.id}
              className={`${isDone ? 'done-card' : ''} ${isJustDone ? 'done-just' : ''}`}
              style={{
                position: 'relative',
                overflow: 'hidden',

                borderRadius: 18,
                padding: '0.85rem 0.95rem',

                background: isDone
                  ? 'linear-gradient(180deg, rgba(34,197,94,0.14), rgba(255,255,255,0.04))'
                  : 'rgba(255,255,255,0.06)',

                border: isDone
                  ? '1px solid rgba(34,197,94,0.40)'
                  : '1px solid rgba(255,255,255,0.10)',

                backdropFilter: 'blur(16px)',
                WebkitBackdropFilter: 'blur(16px)',

                boxShadow: isDone
                  ? '0 12px 34px rgba(0,0,0,0.36), 0 0 0 1px rgba(34,197,94,0.08)'
                  : '0 16px 44px rgba(0,0,0,0.45)',

                opacity: isDone ? 0.88 : 1,
                transition:
                  'border-color 220ms ease, background 220ms ease, box-shadow 220ms ease, opacity 220ms ease',

                // ✅ “完了になった瞬間だけ” は className 側の animation で付与
                animation: isJustDone ? 'doneEnter 900ms ease-out 1' : undefined,
              }}
            >
              {/* ① グリッド質感（いちばん下） */}
              {isDone && (
                <div
                  aria-hidden
                  style={{
                    position: 'absolute',
                    inset: 0,
                    pointerEvents: 'none',

                    backgroundImage: `
                      linear-gradient(
                        0deg,
                        rgba(34,197,94,0.085) 1px,
                        transparent 1px
                      ),
                      linear-gradient(
                        90deg,
                        rgba(34,197,94,0.085) 1px,
                        transparent 1px
                      )
                    `,
                    backgroundSize: '10px 10px',
                    opacity: 1,
                    mixBlendMode: 'screen',

                    maskImage:
                      'radial-gradient(120% 80% at 20% 10%, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.35) 55%, rgba(0,0,0,0.0) 80%)',
                    WebkitMaskImage:
                      'radial-gradient(120% 80% at 20% 10%, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.35) 55%, rgba(0,0,0,0.0) 80%)',
                  }}
                />
              )}

              {/* ② 左アクセントライン */}
              {isDone && (
                <div
                  aria-hidden
                  style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    bottom: 0,
                    width: 5,
                    background:
                      'linear-gradient(180deg, rgba(34,197,94,0.0), rgba(34,197,94,0.65), rgba(34,197,94,0.0))',
                    boxShadow: '0 0 18px rgba(34,197,94,0.22)',
                    borderTopLeftRadius: 18,
                    borderBottomLeftRadius: 18,
                    pointerEvents: 'none',
                  }}
                />
              )}

              {/* ③ シマー（動き） */}
              {isDone && (
                <div
                  aria-hidden
                  className="done-shimmer"
                  style={{
                    position: 'absolute',
                    inset: 0,
                    pointerEvents: 'none',
                    background:
                      'linear-gradient(120deg, transparent 0%, rgba(34,197,94,0.10) 40%, rgba(255,255,255,0.08) 55%, transparent 72%)',
                    transform: 'translateX(-30%)',
                    animation: 'doneShimmer 3.6s ease-in-out infinite',
                    mixBlendMode: 'screen',
                  }}
                />
              )}

              {/* ④ オーラ（いちばん上・近未来感） */}
              {isDone && (
                <div
                  aria-hidden
                  className="done-aura"
                  style={{
                    position: 'absolute',
                    inset: -2,
                    pointerEvents: 'none',
                    background:
                      'radial-gradient(80% 60% at 20% 15%, rgba(34,197,94,0.22) 0%, transparent 60%)',
                    opacity: 0.22, // ✅ 0.16 → 0.22
                    mixBlendMode: 'screen',
                    animation: 'doneAura 5.8s ease-in-out infinite',
                  }}
                />
              )}

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
                    {isDone && (
                      <span
                        style={{
                          flexShrink: 0,
                          fontSize: '0.75rem',
                          fontWeight: 800,
                          letterSpacing: '0.04em',
                          padding: '0.15rem 0.45rem',
                          borderRadius: 9999,
                          border: '1px solid rgba(34,197,94,0.35)',
                          background: 'rgba(34,197,94,0.14)',
                          color: 'rgba(214,255,232,0.92)',
                          boxShadow: '0 8px 24px rgba(34,197,94,0.12)',
                        }}
                      >
                        ✓ DONE
                      </span>
                    )}
                    <div
                      style={{
                        fontWeight: 600,
                        fontSize: '1rem',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',

                        opacity: isDone ? 0.72 : 1,
                        textDecoration: isDone ? 'line-through' : 'none',
                        textDecorationThickness: isDone ? '2px' : undefined,
                        textDecorationColor: isDone
                          ? 'rgba(34,197,94,0.55)'
                          : undefined,
                      }}
                    >
                      {task.title || 'タイトル未設定'}
                    </div>
                  </div>

                  <div style={{ position: 'relative' }}>
                    <button
                      type="button"
                      onClick={(e) => {
                        const rect = (e.currentTarget as HTMLButtonElement).getBoundingClientRect();
                        setMenuState((prev) =>
                          prev?.taskId === task.id ? null : { taskId: task.id, rect }
                        );
                      }}
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
                  </div>
                </div>
                {/* 2行目: 期限 */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    fontSize: '0.8rem',
                    color: (isOverdueNow || isOverdueView)
                      ? 'rgba(255,214,102,.92)'
                      : 'rgba(255,255,255,.62)',
                    marginBottom: '0.4rem',
                  }}
                >
                  <span style={{ marginRight: '0.35rem' }}>
                    {(isOverdueNow || isOverdueView) ? '⚠️' : '🕒'}
                  </span>

                  <span style={{ fontWeight: (isOverdueNow || isOverdueView) ? 700 : 400 }}>
                    {formatDeadline(task.deadline)}
                  </span>
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

                {/* 4行目: メモ（毎週タスクで空でも placeholder を出さず、ラベルだけ残す） */}
                {showContentRow && (
                  <div>
                    <div
                      style={{
                        fontSize: '0.8rem',
                        color: 'rgba(255,255,255,.62)',
                        marginBottom: 2,
                      }}
                    >
                      メモ
                    </div>
                    <EditableTextCell
                      value={baseMemo}
                      placeholder=""   // ✅ ここがポイント：空なら表示しない
                      onSave={async (v) => {
                        const trimmed = v.trim();
                        if (trimmed === baseMemo) return;
                        const prev = task.memo ?? '';
                        onTaskPatched?.(task.id, { memo: trimmed });
                        if (isVirtualTask(task)) return;
                        try {
                          await tasksApi.update(task.id, { memo: trimmed });
                        } catch {
                          onTaskPatched?.(task.id, { memo: prev }); // rollback
                          alert('メモの更新に失敗しました'); // ✅ ついでに文言も合わせる（任意）
                        }
                      }}
                    />
                  </div>
                )}

                {/* ✏️ 編集フォーム */}
                
              </div>
            );
          })}
        </div>

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
                メモ（任意）
                <textarea
                  value={editMemo}
                  onChange={(e) => setEditMemo(e.target.value)}
                  rows={4}
                  style={{
                    padding: '0.65rem 0.9rem',
                    borderRadius: 16,
                    fontSize: '0.9rem',
                    color: 'rgba(255,255,255,.92)',
                    background: 'rgba(255,255,255,.06)',
                    border: '1px solid rgba(255,255,255,.12)',
                    resize: 'vertical',
                    lineHeight: 1.4,
                    whiteSpace: 'pre-wrap',
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
                    const prevTitle = t.title;
                    const prevDeadline = t.deadline;
                    const prevMemo = t.memo ?? ''; 
                    try {
                      const nextMemo = editMemo.trim();
                      const payload: TaskUpdate = {
                        title: editTitle.trim(),
                        deadline: deadlineStr,
                        memo: nextMemo,
                      };
                      // 楽観反映（先に見た目更新）
                      onTaskPatched?.(t.id, { title: payload.title, deadline: payload.deadline, memo: payload.memo,});
                        if (isVirtualTask(t)) {
                          setEditingTaskId(null);
                          return;
                        }
                      await tasksApi.update(t.id, payload);
                      setEditingTaskId(null);
                    } catch (e) {
                      console.error('タスクの更新に失敗しました:', e);
                      onTaskPatched?.(t.id, { title: prevTitle, deadline: prevDeadline, memo: prevMemo, }); // rollback
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

              {isPremium ? (
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
              ) : (
                <button
                  type="button"
                  onClick={() => onRequestUpgrade?.()}
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
                  他の時間を追加（Pro）
                </button>
              )}
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

      {/* ✅ fixedレイヤーのギアメニュー（スタッキング事故を根絶） */}
      {menuState && (
        <>
          {/* 外側クリックで閉じるための透明オーバーレイ */}
          <div
            onClick={() => setMenuState(null)}
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 70,
              background: 'transparent',
            }}
          />

          {/* メニュー本体 */}
          <div
            style={{
              position: 'fixed',
              zIndex: 80,

              // ⚙️ボタンの右下に出す（画面外なら内側に寄せる）
              top: Math.min(menuState.rect.bottom + 8, window.innerHeight - 140),
              left: Math.min(menuState.rect.right - 140, window.innerWidth - 16),
              width: 140,

              borderRadius: 10,
              backgroundColor: '#ffffff',
              boxShadow: '0 12px 30px rgba(15,23,42,0.28)',
              border: '1px solid #e5e7eb',
              overflow: 'hidden',
            }}
          >
            <button
              type="button"
              onClick={() => {
                const task = tasks.find((t) => t.id === menuState.taskId);
                if (task) openEditModal(task);
                setMenuState(null);
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

            <button
              type="button"
              onClick={() => {
                const task = tasks.find((t) => t.id === menuState.taskId);
                if (task) openNotificationModal(task);
                setMenuState(null);
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
        </>
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

  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const handleClick = () => {
    setDraft(value);
    setIsEditing(true);
  };

  // ✅ 編集開始時に caret を末尾へ
  useEffect(() => {
    if (!isEditing) return;

    const el = textareaRef.current;
    if (!el) return;

    // DOM反映後に selection を動かす
    requestAnimationFrame(() => {
      try {
        el.focus();
        const len = el.value.length;
        el.setSelectionRange(len, len);
      } catch {
        // noop（Safari等で万一落ちても編集は継続）
      }
    });
  }, [isEditing]);

  const finish = (commit: boolean) => {
    if (commit && draft !== value) {
      onSave(draft);
    }
    setIsEditing(false);
  };

  const displayText = value ? value.split('\n')[0] : '';
  const lineCount = Math.max(2, draft.split('\n').length);

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      {/* ✅ 編集中は表示テキストを見せない（2重表示を根絶） */}
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

          // ここがポイント：レイアウトは維持して、文字だけ見えなくする
          opacity: isEditing ? 0 : 1,
          pointerEvents: isEditing ? 'none' : 'auto',
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
            top: '100%',
            left: 0,
            marginTop: 6,
            zIndex: 20,
            width: '100%',
          }}
        >
          <textarea
            ref={textareaRef}
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
              width: '100%',
              maxWidth: '100%',
              boxSizing: 'border-box',
              fontSize: '0.9rem',
              padding: '8px 10px',
              borderRadius: 12,
              border: '1px solid rgba(255,255,255,0.14)',
              outline: 'none',
              color: 'rgba(255,255,255,0.92)',
              background: 'rgba(15,23,42,0.72)',
              backdropFilter: 'blur(10px)',
              WebkitBackdropFilter: 'blur(10px)',
              boxShadow:
                '0 14px 34px rgba(0,0,0,0.40), inset 0 1px 0 rgba(255,255,255,0.08)',
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
