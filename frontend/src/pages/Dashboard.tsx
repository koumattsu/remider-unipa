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

const NOTIFY_OVERRIDES_STORAGE_KEY = 'unipa_notify_overrides_v1';

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

export const Dashboard: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [weeklyTemplates, setWeeklyTemplates] = useState<WeeklyTask[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabKey>('today');
  const [isMenuOpen, setIsMenuOpen] = useState(false);

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
    (async () => {
      // 1) 毎週タスクを実タスク化（向こう7日分）
      try {
        await weeklyTasksApi.materialize();
      } catch (e) {
        console.error('weekly materialize 失敗:', e);
        // 失敗しても tasks は出したいので続行
      }

      // 2) 実タスクを取得
      await loadTasks();

      // 3) weeklyテンプレやoverrideもロード
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

  const allTasksWithWeekly: Task[] = useMemo(() => tasks, [tasks]);

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
    () => tasks.filter((t) => isTodayTask(t.deadline)),
    [tasks]
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
