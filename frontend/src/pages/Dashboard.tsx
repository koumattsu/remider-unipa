// frontend/src/pages/Dashboard.tsx

import { useState, useEffect, useMemo } from 'react';
import { Task, TaskCreate, WeeklyTask } from '../types';
import { tasksApi } from '../api/tasks';
import { weeklyTasksApi } from '../api/weeklyTasks';
import { TaskForm } from '../components/TaskForm';
import { TaskList } from '../components/TaskList';
import { NotificationSettings } from '../components/NotificationSettings';
import { TodayTaskList } from '../components/TodayTaskList';
import { StatsView } from '../components/StatsView';
import { WeeklyTaskSettings } from '../components/WeeklyTaskSettings';
import { taskNotificationOverrideApi } from '../api/taskNotificationOverride';

const WEEKLY_SKIP_STORAGE_KEY = 'unipa_weekly_skips_v1';

const NOTIFY_OVERRIDES_STORAGE_KEY = 'unipa_notify_overrides_v1';

type TaskNotificationOptions = {
  morning: boolean;
  offsetsHours: number[];
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


/** localStorage から「スキップした毎週タスクのキー」を読み込み */
const loadWeeklySkipKeys = (): string[] => {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(WEEKLY_SKIP_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
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


/** localStorage に保存 */
const saveWeeklySkipKeys = (keys: string[]) => {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(
    WEEKLY_SKIP_STORAGE_KEY,
    JSON.stringify(Array.from(new Set(keys)))
  );
};

/** 🔔 通知ON/OFFの上書き情報を localStorage に保存 */
const saveNotifyOverrides = (map: Record<number, boolean>) => {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(
    NOTIFY_OVERRIDES_STORAGE_KEY,
    JSON.stringify(map)
  );
};




/** weekly_task_id + 日付 から一意キーを作る */
const makeSkipKey = (weeklyTaskId: number, date: Date): string => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${weeklyTaskId}:${y}-${m}-${d}`;
};

// タブ
type TabKey = 'today' | 'all' | 'stats' | 'weekly' | 'add' | 'settings';

export const Dashboard: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [weeklyTemplates, setWeeklyTemplates] = useState<WeeklyTask[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabKey>('today');
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  // ★ この週だけ非表示にした「毎週タスク」のキー (localStorage と同期)
  const [weeklySkipKeys, setWeeklySkipKeys] = useState<string[]>(() =>
    loadWeeklySkipKeys()
  );

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
    setNotifyOverrides((prev) => {
      const next = { ...prev, [taskId]: value };
      saveNotifyOverrides(next); // ← 変更を永続化
      return next;
    });
  };


  useEffect(() => {
    loadTasks();
    loadWeeklyTemplates();
  }, []);

  const loadTasks = async () => {
    try {
      setIsLoading(true);
      const data = await tasksApi.getAll();
      setTasks(data);
    } catch (error) {
      console.error('課題の取得に失敗しました:', error);
      alert('課題の取得に失敗しました');
    } finally {
      setIsLoading(false);
    }
  };

  const loadWeeklyTemplates = async () => {
    try {
      const data = await weeklyTasksApi.getAll();
      setWeeklyTemplates(data);
    } catch (error) {
      console.error('毎週タスクの取得に失敗しました:', error);
    }
  };

  // JS getDay() (0=日) → 0=月〜6=日の番号に変換
  const toMonZeroWeekday = (jsDay: number) => {
    return (jsDay + 6) % 7;
  };

    const virtualWeeklyTasks: Task[] = useMemo(() => {
    if (weeklyTemplates.length === 0) return [];

    const result: Task[] = [];
    const now = new Date();
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const days = 7; // 今日〜6日後まで

    for (let offset = 0; offset < days; offset++) {
      const day = new Date(start);
      day.setDate(start.getDate() + offset);

      const jsDay = day.getDay(); // 0=日〜6=土
      const weekdayMon0 = toMonZeroWeekday(jsDay); // 0=月〜6=日

      weeklyTemplates.forEach((tpl) => {
        if (!tpl.is_active) return;
        if (tpl.weekday !== weekdayMon0) return;

        const deadline = new Date(
          day.getFullYear(),
          day.getMonth(),
          day.getDate(),
          tpl.time_hour ?? 0,
          tpl.time_minute ?? 0,
          0
        );

        // ★ 表示上の日付（00:00 は前日の 24:00 として扱う）
        const displayDate = new Date(deadline);
        if (displayDate.getHours() === 0 && displayDate.getMinutes() === 0) {
          displayDate.setDate(displayDate.getDate() - 1);
        }

        // ★ この (weekly_task_id, 表示日) にスキップ設定があれば生成しない
        const skipKey = makeSkipKey(tpl.id, displayDate);
        if (weeklySkipKeys.includes(skipKey)) {
          return;
        }

        const virtualId = -1 * (tpl.id * 10 + offset);

        const virtualTask: Task = {
          id: virtualId,
          title: tpl.title,
          course_name: tpl.course_name || '',
          memo: tpl.memo || '',
          deadline: deadline.toISOString(),
          is_done: false,
        } as Task;

        result.push(virtualTask);
      });

    }

    return result;
  }, [weeklyTemplates, weeklySkipKeys]);


    const allTasksWithWeekly: Task[] = useMemo(
    () => [...tasks, ...virtualWeeklyTasks],
    [tasks, virtualWeeklyTasks]
  );


  // 🔍 24:00 ロジックを考慮した「今日のタスク」判定
  const isTodayTask = (deadline: string) => {
    const raw = new Date(deadline);
    const effective = new Date(raw);

    if (effective.getHours() === 0 && effective.getMinutes() === 0) {
      effective.setDate(effective.getDate() - 1);
    }

    const now = new Date();

    const toYMD = (date: Date) => ({
      y: date.getFullYear(),
      m: date.getMonth(),
      d: date.getDate(),
    });

    const dY = toYMD(effective);
    const tY = toYMD(now);

    return dY.y === tY.y && dY.m === tY.m && dY.d === tY.d;
  };

    const todayTasks = useMemo(
    () =>
      [...tasks, ...virtualWeeklyTasks].filter((t) =>
        isTodayTask(t.deadline)
      ),
    [tasks, virtualWeeklyTasks]
  );


  // ➕ 右下のプラスボタンの挙動
  const handleFabClick = async () => {
    // 「全部」タブで＋を押したら、課題追加画面に飛ばす
    if (activeTab === 'all') {
      setActiveTab('add');
      return;
    }

    // 今日タブ：今日のタスクをサクッと追加
    if (activeTab === 'today') {
      const title = window.prompt('今日のタスクのタイトルを入力してください');
      if (!title || !title.trim()) {
        return;
      }

      const now = new Date();
      const tomorrow = new Date(
        now.getFullYear(),
        now.getMonth(),
        now.getDate() + 1,
        0,
        0,
        0
      );

      const payload: TaskCreate= {
        title: title.trim(),
        course_name: '',
        deadline: tomorrow.toISOString(),
        memo: '',
        should_notify: true, 
      };

      try {
        await tasksApi.create(payload);
        await loadTasks();
      } catch (error) {
        console.error('今日のタスク追加に失敗しました:', error);
        alert('今日のタスク追加に失敗しました');
      }
    }
  };

  // ★ 仮の毎週タスクを「この週だけ」非表示にする（ブラウザに保存）
  const handleVirtualWeeklyDelete = (task: Task) => {
    // id < 0 を元に weekly_task_id を復元
    const encoded = -task.id;
    const weeklyTaskId = Math.floor(encoded / 10);
    if (weeklyTaskId <= 0) return;

    const raw = new Date(task.deadline);
    const effective = new Date(raw);

    // 00:00 の場合は前日の 24:00 として扱う
    if (effective.getHours() === 0 && effective.getMinutes() === 0) {
      effective.setDate(effective.getDate() - 1);
    }

    const key = makeSkipKey(weeklyTaskId, effective);

    setWeeklySkipKeys((prev) => {
      if (prev.includes(key)) return prev;
      const next = [...prev, key];
      saveWeeklySkipKeys(next);
      return next;
    });
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
            <TaskList
              tasks={allTasksWithWeekly}
              onTaskUpdated={loadTasks}
              onVirtualTaskDelete={handleVirtualWeeklyDelete}
              notifyOverrides={notifyOverrides}
              onNotifyChange={handleNotifyChange}
              // ★ 追加
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
              onTemplatesChanged={loadWeeklyTemplates}
            />
          </>
        );
      case 'add':
        return (
          <>
            <h1 style={{ marginBottom: '1rem' }}>課題を追加</h1>
            <TaskForm
              onTaskCreated={async () => {
                await loadTasks();
                setActiveTab('all'); // 追加完了後に「全部」へ戻る
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

  return (
    <div
      style={{
        maxWidth: '1200px',
        margin: '0 auto',
        padding: '0.75rem 1rem 4.5rem',
      }}
    >
      {/* ヘッダー（左上ハンバーガー） */}
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '0.75rem',
        }}
      >
        <button
          onClick={() => setIsMenuOpen(true)}
          aria-label="メニュー"
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            border: 'none',
            backgroundColor: '#f0f0f0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
          }}
        >
          {/* 三本線 */}
          <div
            style={{
              width: 18,
              height: 2,
              backgroundColor: '#333',
              boxShadow: '0 5px 0 #333, 0 -5px 0 #333',
            }}
          />
        </button>
        {/* 中央の「UniPA Reminder」は空にする */}
        <div
          style={{
            fontWeight: 600,
            fontSize: '1rem',
          }}
        />
        <div style={{ width: 32 }} />
      </header>

      {renderContent()}

      {/* ➕ フローティングアクションボタン */}
      {(activeTab === 'today' || activeTab === 'all') && (
        <button
          onClick={handleFabClick}
          style={{
            position: 'fixed',
            right: '1.5rem',
            bottom: '4.8rem',
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
          maxWidth: '1200px',
          padding: '0.4rem 1rem',
          backgroundColor: '#ffffff',
          borderTop: '1px solid #ddd',
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
              backgroundColor: '#fff',
              padding: '1rem',
              boxShadow: '2px 0 12px rgba(0,0,0,0.2)',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.5rem',
            }}
          >
            <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>メニュー</div>

            <MenuItem
              label="課題を追加"
              onClick={() => {
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
                  border: '1px solid #ccc',
                  backgroundColor: '#f8f8f8',
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
        color: active ? '#007bff' : '#666',
        fontWeight: active ? 600 : 400,
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
      border: 'none',
      background: 'none',
      padding: '0.5rem 0.2rem',
      fontSize: '0.9rem',
      cursor: 'pointer',
    }}
  >
    {label}
  </button>
);
