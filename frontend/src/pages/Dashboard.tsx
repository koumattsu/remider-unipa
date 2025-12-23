// frontend/src/pages/Dashboard.tsx

import { useState, useEffect, useMemo } from 'react';
import { Task, WeeklyTask } from '../types';
import { tasksApi } from '../api/tasks';
import { weeklyTasksApi } from '../api/weeklyTasks';
import { TaskForm } from '../components/TaskForm';
import { TaskList } from '../components/TaskList';
import { NotificationSettings } from '../components/NotificationSettings';
import { TodayTaskList } from '../components/TodayTaskList';
import { StatsView } from '../components/StatsView';
import { WeeklyTaskSettings } from '../components/WeeklyTaskSettings';
import { taskNotificationOverrideApi } from '../api/taskNotificationOverride';
import { isTodayTaskJst, getAllTasksByViewMode } from '../utils/taskTime';

const NOTIFY_OVERRIDES_STORAGE_KEY = 'unipa_notify_overrides_v1';
const TASKS_CACHE_KEY = 'unipa_tasks_cache_v1';
const WEEKLY_CACHE_KEY = 'unipa_weekly_templates_cache_v1';

type CachedPayload<T> = { savedAt: number; data: T };

const loadCache = <T,>(key: string): CachedPayload<T> | null => {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CachedPayload<T>;
    if (!parsed || typeof parsed !== 'object') return null;
    if (!('data' in parsed)) return null;
    return parsed;
  } catch {
    return null;
  }
};

const saveCache = <T,>(key: string, data: T) => {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(
      key,
      JSON.stringify({ savedAt: Date.now(), data } satisfies CachedPayload<T>)
    );
  } catch {
    // localStorage容量などで失敗してもアプリは動かす
  }
};

type TaskNotificationOptions = {
  morning: boolean;
  offsetsHours: number[];
};

// Dashboard.tsx 内に追加（TaskList.tsx と同じ考え方）
const NOTIFICATION_STORAGE_KEY = 'unipa_notification_settings_v1';

type StoredNotificationSettings = {
  enableMorning: boolean;
  dailyDigestTime: string;
  reminderOffsetsHours: number[];
};

const loadGlobalNotificationDefaults = (): TaskNotificationOptions => {
  try {
    const raw = window.localStorage.getItem(NOTIFICATION_STORAGE_KEY);
    if (!raw) return { morning: true, offsetsHours: [3] };

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
  } catch {
    return { morning: true, offsetsHours: [3] };
  }
};


const TASK_NOTIFY_OPTIONS_STORAGE_KEY = 'unipa_task_notify_options_v1';

const loadTaskNotifyOptions = (): Record<number, TaskNotificationOptions> => {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(TASK_NOTIFY_OPTIONS_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
};

const saveTaskNotifyOptions = (map: Record<number, TaskNotificationOptions>) => {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(
    TASK_NOTIFY_OPTIONS_STORAGE_KEY,
    JSON.stringify(map)
  );
};

/** 🔔 localStorage から通知ON/OFFの上書き情報を読み込み */
const loadNotifyOverrides = (): Record<number, boolean> => {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(NOTIFY_OVERRIDES_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
};

/** 🔔 通知ON/OFFの上書き情報を localStorage に保存 */
const saveNotifyOverrides = (map: Record<number, boolean>) => {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(
    NOTIFY_OVERRIDES_STORAGE_KEY,
    JSON.stringify(map)
  );
};

// タブ
type TabKey = 'today' | 'all' | 'stats' | 'weekly' | 'add' | 'settings';
type AllViewMode = 'active' | 'overdue' | 'incomplete';

export const Dashboard: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>(() => {
    const cached = loadCache<Task[]>(TASKS_CACHE_KEY);
    return cached?.data ?? [];
  });

  // ✅ ローカル即反映（state + cache 同期）
  const patchTaskLocal = (taskId: number, patch: Partial<Task>) => {
    setTasks((prev) => {
      const next = prev.map((t) => (t.id === taskId ? { ...t, ...patch } : t));
      saveCache(TASKS_CACHE_KEY, next);
      return next;
    });
  };

  // ✅ 追加：仮タスクも含めて先にUIに足す
  const addTaskLocal = (task: Task) => {
    setTasks((prev) => {
      const next = [task, ...prev]; // 先頭に追加（見た目: 即出る）
      saveCache(TASKS_CACHE_KEY, next);
      return next;
    });
  };

  // ✅ 追加：仮IDのタスクを、サーバから返った実タスクで置換
  const replaceTaskLocal = (tempId: number, realTask: Task) => {
    setTasks((prev) => {
      const next = prev.map((t) => (t.id === tempId ? realTask : t));
      saveCache(TASKS_CACHE_KEY, next);
      return next;
    });
  };

  const removeTasksLocal = (ids: number[]) => {
    const idSet = new Set(ids);
    setTasks((prev) => {
      const next = prev.filter((t) => !idSet.has(t.id));
      saveCache(TASKS_CACHE_KEY, next);
      return next;
    });
  };

  const [weeklyTemplates, setWeeklyTemplates] = useState<WeeklyTask[]>(() => {
    const cached = loadCache<WeeklyTask[]>(WEEKLY_CACHE_KEY);
    return cached?.data ?? [];
  });

  const [isLoading, setIsLoading] = useState(() => {
    const cached = loadCache<Task[]>(TASKS_CACHE_KEY);
    return cached ? false : true;
  });

  const [activeTab, setActiveTab] = useState<TabKey>('today');
  const [allViewMode, setAllViewMode] = useState<AllViewMode>('active');
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [addDefaultDeadlineDate, setAddDefaultDeadlineDate] = useState<string | undefined>(undefined);

    // 🔔 通知ON/OFFの上書き状態（today / all で共有）
  //    → 初期値を localStorage から読み込む
  const [notifyOverrides, setNotifyOverrides] =
    useState<Record<number, boolean>>(() => loadNotifyOverrides());

  // 🔔 タスクごとの通知詳細（朝ON/OFF + ◯時間前の配列）
  const [taskNotifyOptions, setTaskNotifyOptions] =
    useState<Record<number, TaskNotificationOptions>>(() =>
      loadTaskNotifyOptions()
    );

  // 🔔 タスクごとの通知設定が変わったときのハンドラ
  const handleTaskNotifyOptionsChange = async (
    taskId: number,
    value: TaskNotificationOptions
  ) => {
    // id > 0 = 実タスク → DB にも保存する
    if (taskId > 0) {
      try {
        await taskNotificationOverrideApi.upsert(taskId, {
          enable_morning: value.morning,
          reminder_offsets_hours: value.offsetsHours,
        });
      } catch (e) {
        console.error('タスク通知設定の保存に失敗しました:', e);
        alert('タスク通知設定の保存に失敗しました');
        return; // 失敗したらフロント側の状態は変えない
      }
    }
    // id < 0 = 仮想タスク（毎週タスク） → これまで通りフロントだけで保持
    setTaskNotifyOptions((prev) => {
      const next = { ...prev, [taskId]: value };
      saveTaskNotifyOptions(next); // localStorage にもキャッシュ
      return next;
    });
  };

  const handleNotifyChange = (taskId: number, value: boolean) => {
    if (taskId > 0) return; // 実タスク(id>0)はDB(should_notify)が真実なのでlocalStorageには保存しない
    setNotifyOverrides((prev) => {
      const next = { ...prev, [taskId]: value };
      saveNotifyOverrides(next); // ← 変更を永続化
      return next;
    });
  };

  useEffect(() => {
    // まずはキャッシュで描画済み（isLoadingもfalseになってる想定）
    // 裏で最新化
    (async () => {
      try {
        await weeklyTasksApi.materialize();
      } catch (e) {
        console.error('weekly materialize 失敗:', e);
      }

      // ここからは silent で（画面をブロックしない）
      await loadTasks({ silent: true });
      await loadWeeklyTemplates();
      await loadTaskNotificationOverrides();
    })();
  }, []);

  const loadTaskNotificationOverrides = async () => {
    try {
      const rows = await taskNotificationOverrideApi.getAll();

      // DBの結果を Record<number, TaskNotificationOptions> に変換
      const fromDb: Record<number, TaskNotificationOptions> = {};
      const defaults = loadGlobalNotificationDefaults();
      for (const r of rows) {
        const morning = r.enable_morning ?? defaults.morning;
        const offsetsRaw = r.reminder_offsets_hours ?? defaults.offsetsHours;
        const offsets = offsetsRaw
          .map((n: any) => Number(n))
          .filter((n) => Number.isFinite(n) && n > 0);
        fromDb[r.task_id] = { morning, offsetsHours: offsets.length ? offsets : [3] };
      }

      setTaskNotifyOptions((prev) => {
        // 仮想タスク(id<0)だけ残す
        const virtualOnly: Record<number, TaskNotificationOptions> = {};
        for (const [k, v] of Object.entries(prev)) {
          const id = Number(k);
          if (id < 0) virtualOnly[id] = v;
        }

        const next = { ...virtualOnly, ...fromDb };
        saveTaskNotifyOptions(next); // キャッシュ（仮想も含めて）
        return next;
      });
    } catch (e) {
      console.error('タスク通知設定(override)の取得に失敗しました:', e);
      // 失敗してもlocalStorageのキャッシュで動くのでalertしない（UX優先）
    }
  };

  const loadTasks = async (opts?: { silent?: boolean }) => {
    const silent = opts?.silent ?? false;

    try {
      if (!silent) setIsLoading(true);
      const data = await tasksApi.getAll();
      setTasks(data);
      saveCache(TASKS_CACHE_KEY, data);
    } catch (error) {
      console.error('課題の取得に失敗しました:', error);
      // キャッシュがあるなら alert しない（UX優先）
      const hasCache = !!loadCache<Task[]>(TASKS_CACHE_KEY);
      if (!hasCache) alert('課題の取得に失敗しました');
    } finally {
      if (!silent) setIsLoading(false);
    }
  };

  const loadWeeklyTemplates = async () => {
    try {
      const data = await weeklyTasksApi.getAll();
      setWeeklyTemplates(data);
      saveCache(WEEKLY_CACHE_KEY, data);
    } catch (error) {
      console.error('毎週タスクの取得に失敗しました:', error);
    }
  };

  const allTasksWithWeekly: Task[] = useMemo(() => tasks, [tasks]);

  const allDisplayTasks = useMemo(() => {
    return getAllTasksByViewMode(allTasksWithWeekly, allViewMode);
  }, [allTasksWithWeekly, allViewMode]);

  const todayTasks = useMemo(() => {
    return tasks
      .filter((t) => isTodayTaskJst(t.deadline))
      .sort((a, b) => {
        // 未完 → 完了
        if (a.is_done !== b.is_done) {
          return a.is_done ? 1 : -1;
        }
        // 同じ状態なら締切順
        return new Date(a.deadline).getTime() - new Date(b.deadline).getTime();
      });
  }, [tasks]);

  const formatYmd = (d: Date) => {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  };

  // ➕ 右下のプラスボタンの挙動
  const handleFabClick = async () => {
    if (activeTab === 'all') {
      setAddDefaultDeadlineDate(undefined); // ★クリア（従来通り空で追加）
      setActiveTab('add');
      return;
    }

    if (activeTab === 'today') {
      setAddDefaultDeadlineDate(formatYmd(new Date())); // ★今日をプリセット
      setActiveTab('add');
      return;
    }
  };

  if (isLoading) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center' }}>
        読み込み中...
      </div>
    );
  }

  // メインコンテンツの切り替え
  const renderContent = () => {
    switch (activeTab) {
      case 'today':
        return (
          <>
            <TodayTaskList
              tasks={todayTasks}
              onTaskUpdated={loadTasks}
              onTaskPatched={patchTaskLocal}
              onTasksRemoved={removeTasksLocal}
              notifyOverrides={notifyOverrides}
              onNotifyChange={handleNotifyChange}
              // ★ 追加
              taskNotificationOverrides={taskNotifyOptions}
              onTaskNotificationOptionsChange={handleTaskNotifyOptionsChange}
            />
          </>
        );

      case 'all':
        return (
          <>
            <AllModeDropdown value={allViewMode} onChange={setAllViewMode} />
            <TaskList
              tasks={allDisplayTasks}
              isOverdueView={allViewMode === 'overdue'}
              onTaskUpdated={loadTasks}
              onTaskPatched={patchTaskLocal}
              onTasksRemoved={removeTasksLocal}
              notifyOverrides={notifyOverrides}
              onNotifyChange={handleNotifyChange}
              taskNotificationOverrides={taskNotifyOptions}
              onTaskNotificationOptionsChange={handleTaskNotifyOptionsChange}
            />
          </>
        );

      case 'stats':
        return (
          <>
            <h1 style={{ marginBottom: '1rem' }}>分析 / 統計</h1>
            <StatsView tasks={tasks} />
          </>
        );
      case 'weekly':
        return (
          <>
            <h1 style={{ marginBottom: '1rem' }}>毎週タスク設定</h1>
            <p
              style={{
                marginBottom: '0.75rem',
                fontSize: '0.85rem',
                color: '#666',
              }}
            >
              例）毎週水曜の授業アンケート、毎週金曜のレポート確認など、
              定期的に発生するタスクを登録しておくと、
              全タスク一覧に「向こう1週間分」が自動で表示されます。
            </p>
            <WeeklyTaskSettings
              templates={weeklyTemplates}
              onTemplatesChanged={async () => {
                await loadWeeklyTemplates();
                try {
                  await weeklyTasksApi.materialize();
                } catch (e) {
                  console.error('weekly materialize 失敗:', e);
                }
                await loadTasks();
              }}
            />
          </>
        );
      case 'add':
        return (
          <>
            <h1 style={{ marginBottom: '1rem' }}>課題を追加</h1>
            <TaskForm
              defaultDeadlineDate={addDefaultDeadlineDate}
              onTaskAddedLocal={addTaskLocal}
              onTaskReplacedLocal={replaceTaskLocal}
              onTaskCreateFailedLocal={(tempId) => removeTasksLocal([tempId])}
              onTaskCreated={async () => {
                setAddDefaultDeadlineDate(undefined);        // ★作成後クリア（重要）
                setActiveTab('all');
              }}
            />
          </>
        );
      case 'settings':
        return (
          <>
            <h1 style={{ marginBottom: '1rem' }}>通知設定</h1>
            <NotificationSettings />
          </>
        );
      default:
        return null;
    }
  };

  const ALL_MODE_ITEMS: { key: AllViewMode; label: string; desc: string; icon: string }[] = [
    { key: 'active', label: '管理中', desc: '期限内 + 期限超過≤24h（未完）', icon: '🟦' },
    { key: 'overdue', label: '期限切れ未完了', desc: '期限超過（未完）', icon: '⚠️' },
    { key: 'incomplete', label: '締切内の未完了', desc: '期限内（未完）', icon: '🕒' },
  ];

  const AllModeDropdown: React.FC<{
    value: AllViewMode;
    onChange: (v: AllViewMode) => void;
  }> = ({ value, onChange }) => {
    const [open, setOpen] = useState(false);

    useEffect(() => {
      const onDocClick = () => setOpen(false);
      if (open) document.addEventListener('click', onDocClick);
      return () => document.removeEventListener('click', onDocClick);
    }, [open]);

    const current = ALL_MODE_ITEMS.find((x) => x.key === value)!;

    return (
      <div style={{ marginBottom: '0.75rem', position: 'relative' }} onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          onClick={() => setOpen((p) => !p)}
          style={{
            width: '100%',
            padding: '0.7rem 0.85rem',
            borderRadius: 18,
            border: '1px solid rgba(255,255,255,.12)',
            background:
              'radial-gradient(circle at 20% 0%, rgba(0,212,255,.22), rgba(255,255,255,.06) 45%, rgba(255,255,255,.04))',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            boxShadow: '0 14px 40px rgba(0,0,0,.38)',
            color: 'rgba(255,255,255,.92)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 10,
            cursor: 'pointer',
          }}
          aria-label="表示モードを切り替え"
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
            <div style={{ fontSize: '0.92rem', fontWeight: 700, letterSpacing: '0.02em' }}>
              <span style={{ marginRight: 8 }}>{current.icon}</span>
              {current.label}
            </div>
            <div style={{ fontSize: '0.78rem', color: 'rgba(255,255,255,.62)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {current.desc}
            </div>
          </div>
          <div style={{ opacity: 0.9, fontSize: '1.05rem' }}>{open ? '▴' : '▾'}</div>
        </button>

        {open && (
          <div
            style={{
              position: 'absolute',
              top: 'calc(100% + 10px)',
              left: 0,
              right: 0,
              borderRadius: 18,
              border: '1px solid rgba(255,255,255,.12)',
              background: 'rgba(10, 12, 18, .86)',
              backdropFilter: 'blur(18px)',
              WebkitBackdropFilter: 'blur(18px)',
              boxShadow: '0 18px 60px rgba(0,0,0,.55)',
              overflow: 'hidden',
              zIndex: 120,
            }}
          >
            {ALL_MODE_ITEMS.map((item) => {
              const active = item.key === value;
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => {
                    onChange(item.key);
                    setOpen(false);
                  }}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    padding: '0.75rem 0.85rem',
                    border: 'none',
                    background: active ? 'rgba(0,212,255,.12)' : 'transparent',
                    color: 'rgba(255,255,255,.92)',
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 3,
                  }}
                >
                  <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>
                    <span style={{ marginRight: 8 }}>{item.icon}</span>
                    {item.label}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'rgba(255,255,255,.62)' }}>
                    {item.desc}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    );
  };

  return (
    <div
      style={{
        maxWidth: '420px',
        margin: '0 auto',
        padding: '0.9rem 1rem calc(5.2rem + env(safe-area-inset-bottom))',
        minHeight: '100dvh',
      }}
    >

      {/* ヘッダー（左上ハンバーガー） */}
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '0.9rem',
        }}
      >
        <button
          onClick={() => setIsMenuOpen(true)}
          aria-label="メニュー"
          style={{
            width: 36,
            height: 36,
            borderRadius: 12,
            background: 'rgba(255,255,255,.07)',
            border: '1px solid rgba(255,255,255,.10)',
            backdropFilter: 'blur(18px)',
            WebkitBackdropFilter: 'blur(18px)',
            color: 'rgba(255,255,255,.92)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
          }}
        >
          <div
            style={{
              width: 18,
              height: 2,
              backgroundColor: 'rgba(255,255,255,.85)',
              boxShadow:
                '0 6px 0 rgba(255,255,255,.85), 0 -6px 0 rgba(255,255,255,.85)',
            }}
          />
        </button>

        <div
          style={{
            fontWeight: 700,
            fontSize: '0.95rem',
            letterSpacing: '0.08em',
            color: 'rgba(255,255,255,.82)',
            userSelect: 'none',
          }}
        >
          UNIPA REMINDER
        </div>

        <div style={{ width: 36 }} />
      </header>

      {renderContent()}

      {/* ➕ フローティングアクションボタン */}
      {(activeTab === 'today' || activeTab === 'all') && (
        <button
          onClick={handleFabClick}
          style={{
            position: 'fixed',
            right: '1.5rem',
            bottom: 'calc(4.8rem + env(safe-area-inset-bottom))',
            width: '56px',
            height: '56px',
            borderRadius: '50%',
            border: 'none',
            background:
              'radial-gradient(circle at 30% 0, #ffffff 0, #00d4ff 35%, #0066ff 100%)',
            color: '#fff',
            fontSize: '2rem',
            lineHeight: 1,
            boxShadow: '0 0 18px rgba(0, 212, 255, 0.7)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 150,
          }}
          aria-label={
            activeTab === 'today'
              ? '今日のタスクを追加'
              : '課題追加画面へ移動'
          }
        >
          +
        </button>
      )}

      {/* 下部ナビゲーション */}
      <nav
        style={{
          position: 'fixed',
          left: 0,
          right: 0,
          bottom: 0,
          margin: '0 auto',
          maxWidth: '420px',
          padding: '0.55rem 1rem calc(0.55rem + env(safe-area-inset-bottom))',
          background: 'rgba(10, 12, 18, .72)',
          borderTop: '1px solid rgba(255,255,255,.10)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          display: 'flex',
          justifyContent: 'space-around',
          alignItems: 'center',
          zIndex: 100,
        }}
      >

        <TabButton
          label="全部"
          icon="📋"
          active={activeTab === 'all'}
          onClick={() => setActiveTab('all')}
        />
        <TabButton
          label="今日"
          icon="☀️"
          active={activeTab === 'today'}
          onClick={() => setActiveTab('today')}
        />
        <TabButton
          label="分析"
          icon="📊"
          active={activeTab === 'stats'}
          onClick={() => setActiveTab('stats')}
        />
      </nav>

      {/* ハンバーガーメニューのオーバーレイ */}
      {isMenuOpen && (
        <div
          onClick={() => setIsMenuOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.3)',
            zIndex: 200,
            display: 'flex',
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: '70%',
              maxWidth: 260,
              background: 'var(--card2)',
              border: '1px solid var(--bd)',
              backdropFilter: 'blur(18px)',
              WebkitBackdropFilter: 'blur(18px)',
              padding: '1rem',
              boxShadow: '2px 0 12px rgba(0,0,0,0.2)',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.5rem',
            }}
          >
            <div style={{ fontWeight: 600, marginBottom: '0.5rem', color: 'rgba(255,255,255,.88)' }}>メニュー</div>

            <MenuItem
              label="課題を追加"
              onClick={() => {
                setAddDefaultDeadlineDate(undefined); 
                setActiveTab('add');
                setIsMenuOpen(false);
              }}
            />
            <MenuItem
              label="通知設定"
              onClick={() => {
                setActiveTab('settings');
                setIsMenuOpen(false);
              }}
            />
            <MenuItem
              label="毎週タスク設定"
              onClick={() => {
                setActiveTab('weekly');
                setIsMenuOpen(false);
              }}
            />

            <div style={{ marginTop: '0.5rem' }}>
              <button
                onClick={() => setIsMenuOpen(false)}
                style={{
                  padding: '0.4rem 0.8rem',
                  fontSize: '0.85rem',
                  borderRadius: '4px',
                  background: 'rgba(255,255,255,.10)',
                  border: '1px solid rgba(255,255,255,.14)',
                  color: 'rgba(255,255,255,.88)',
                  cursor: 'pointer',
                }}
              >
                閉じる
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

interface TabButtonProps {
  label: string;
  icon: string;
  active: boolean;
  onClick: () => void;
}

const TabButton: React.FC<TabButtonProps> = ({
  label,
  icon,
  active,
  onClick,
}) => {
  return (
    <button
      onClick={onClick}
      style={{
        flex: 1,
        border: 'none',
        background: 'none',
        padding: '0.4rem 0.6rem',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '0.1rem',
        fontSize: '0.8rem',
        color: active ? 'var(--accent)' : 'rgba(255,255,255,.60)',
        fontWeight: active ? 700 : 500,
        cursor: 'pointer',
      }}
    >
      <span style={{ fontSize: '1.2rem' }}>{icon}</span>
      <span>{label}</span>
    </button>
  );
};

interface MenuItemProps {
  label: string;
  onClick: () => void;
}

const MenuItem: React.FC<MenuItemProps> = ({ label, onClick }) => (
  <button
    onClick={onClick}
    style={{
      width: '100%',
      textAlign: 'left',
      border: '1px solid rgba(255,255,255,.10)',
      background: 'rgba(255,255,255,.06)',
      padding: '0.65rem 0.6rem',
      fontSize: '0.95rem',
      cursor: 'pointer',
      color: 'rgba(255,255,255,.92)',
      borderRadius: 10,
      backdropFilter: 'blur(6px)',
      WebkitBackdropFilter: 'blur(6px)',
    }}
  >
    {label}
  </button>
);
