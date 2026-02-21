// frontend/src/pages/Dashboard.tsx

import { useState, useEffect, useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { Task, WeeklyTask } from '../types';
import { tasksApi } from '../api/tasks';
import { weeklyTasksApi } from '../api/weeklyTasks';
import { fetchInAppNotifications, dismissInAppNotification, fetchInAppNotificationsSummary } from '../api/notifications';
import type { InAppNotification } from '../api/notifications';
import { fetchLatestNotificationRun as fetchLatestNotificationRunApi } from '../api/notificationRuns';
import type { NotificationRun } from '../api/notificationRuns';
import { TaskForm } from '../components/TaskForm';
import { TaskList } from '../components/TaskList';
import { NotificationSettings } from '../components/NotificationSettings';
import { TodayTaskList } from '../components/TodayTaskList';
import { StatsView } from '../components/StatsView';
import { WeeklyTaskSettings } from '../components/WeeklyTaskSettings';
import { taskNotificationOverrideApi } from '../api/taskNotificationOverride';
import { authApi } from '../api/auth';
import { settingsApi } from '../api/settings';
import { isTodayTaskJst, getAllTasksByViewMode } from '../utils/taskTime';

const NOTIFY_OVERRIDES_STORAGE_KEY = 'unipa_notify_overrides_v1';
const TASKS_CACHE_KEY = 'unipa_tasks_cache_v1';
const WEEKLY_CACHE_KEY = 'unipa_weekly_templates_cache_v1';
const NOTIF_LAST_SEEN_TOTAL_KEY = 'unipa_notif_last_seen_total_v1';

const loadNotifLastSeenTotal = (): number => {
  if (typeof window === 'undefined') return 0;
  try {
    const raw = window.localStorage.getItem(NOTIF_LAST_SEEN_TOTAL_KEY);
    const n = raw ? Number(raw) : 0;
    return Number.isFinite(n) ? n : 0;
  } catch {
    return 0;
  }
};

const saveNotifLastSeenTotal = (n: number) => {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(NOTIF_LAST_SEEN_TOTAL_KEY, String(n));
  } catch {}
};

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
  enableWebpush?: boolean;
};

const loadGlobalNotificationDefaults = (): TaskNotificationOptions => {
  try {
    const raw = window.localStorage.getItem(NOTIFICATION_STORAGE_KEY);
    if (!raw) return { morning: true, offsetsHours: [1] };

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
      offsetsHours: uniqueOffsets.length > 0 ? uniqueOffsets : [1],
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
type TabKey = 'today' | 'all' | 'stats' | 'weekly' | 'add' | 'settings' | 'notifications';
type AllViewMode = 'active' | 'overdue' | 'incomplete';

export const Dashboard: React.FC = () => {
  // ✅ 通知本文の表示用：括弧「( … ) / （ … ）」はUIに出さない（資産のbody自体は保持）
  const formatNotifBodyForUi = (body: string) => {
    return (body ?? '')
      .split('\n')
      .map((line) =>
        line
          // 半角/全角の括弧と中身を削除
          .replace(/[\(（][^)\）]*[\)）]/g, '')
          // 余分なスペースを整理（行末はtrimEndでOK）
          .replace(/[ \t]{2,}/g, ' ')
          .trimEnd()
      )
      .join('\n')
      .trim();
  };

  const [globalNotificationsEnabled, setGlobalNotificationsEnabled] = useState<boolean>(() => {
    try {
      const raw = window.localStorage.getItem(NOTIFICATION_STORAGE_KEY);
      if (!raw) return true; // ✅ 初期はON扱い
      const parsed = JSON.parse(raw) as StoredNotificationSettings;
      // enableWebpush が無い旧データは true 扱い（事故りにくい）
      return parsed?.enableWebpush !== undefined ? !!parsed.enableWebpush : true;
    } catch {
      return true;
    }
  });

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

  const location = useLocation();

  const [activeTab, setActiveTab] = useState<TabKey>('today');
  const [allViewMode, setAllViewMode] = useState<AllViewMode>('active');
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [addDefaultDeadlineDate, setAddDefaultDeadlineDate] = useState<string | undefined>(undefined);
  // 🔔 ベル（アプリ内通知）
  const [notifs, setNotifs] = useState<InAppNotification[]>([]);
  const [notifsLoading, setNotifsLoading] = useState(false);
  const [notifsError, setNotifsError] = useState<string | null>(null);
  const [notifBadgeCount, setNotifBadgeCount] = useState<number>(0);
  const [notifLastSeenTotal, setNotifLastSeenTotal] = useState<number>(() => loadNotifLastSeenTotal());
  // 🛠 最新 NotificationRun（admin用）
  const [latestRun, setLatestRun] = useState<NotificationRun | null>(null);
  const [latestRunLoading, setLatestRunLoading] = useState(false);
  const [latestRunError, setLatestRunError] = useState<string | null>(null);
  const [showRunDetails, setShowRunDetails] = useState(false);
  const [showAllReasons, setShowAllReasons] = useState(false);
  const [plan, setPlan] = useState<string>('free');

  // 🔔 通知ON/OFFの上書き状態（today / all で共有）
  //    → 初期値を localStorage から読み込む
  const [notifyOverrides, setNotifyOverrides] =
    useState<Record<number, boolean>>(() => loadNotifyOverrides());

  // 🔔 タスクごとの通知詳細（朝ON/OFF + ◯時間前の配列）
  const [taskNotifyOptions, setTaskNotifyOptions] =
    useState<Record<number, TaskNotificationOptions>>(() =>
      loadTaskNotifyOptions()
    );

  const refreshNotifBadge = async () => {
    try {
      const s = await fetchInAppNotificationsSummary();
      const inapp = (s as any)?.inapp;
      const total = Number(inapp?.total ?? 0) || 0;
      const lastSeen = notifLastSeenTotal || 0;
      const newCount = Math.max(0, total - lastSeen);
      setNotifBadgeCount(newCount);
    } catch (e) {
      // 失敗してもUIは壊さない
    }
  };

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
      // ✅ まずは認証確立（guest含む）
      let me: any = null;

      try {
        me = await authApi.getCurrentUser();
      } catch (e) {
        console.warn('[boot] auth/me failed -> redirect to /login', e);
        // ✅ guest廃止：未ログインは必ず/loginへ
        window.location.hash = '/login';
        return;
      }

      // ✅ ここまで来たら認証OK
      setPlan(String(me?.plan ?? 'free'));

      // ✅ SSOT: グローバル通知（親）を取得して確定（localStorageより強い）
      try {
        const s = await settingsApi.getNotification();
        const enabled = !!(s as any)?.enable_webpush;
        setGlobalNotificationsEnabled(enabled);

        // localStorageも更新（NotificationSettings未訪問でもズレない）
        try {
          const raw = window.localStorage.getItem(NOTIFICATION_STORAGE_KEY);
          const prev = raw ? (JSON.parse(raw) as StoredNotificationSettings) : null;
          const next: StoredNotificationSettings = {
            enableMorning: prev?.enableMorning ?? true,
            dailyDigestTime: prev?.dailyDigestTime ?? '08:00',
            reminderOffsetsHours: prev?.reminderOffsetsHours ?? [1],
            enableWebpush: enabled,
          };
          window.localStorage.setItem(NOTIFICATION_STORAGE_KEY, JSON.stringify(next));
        } catch {}
      } catch (e) {
        console.warn('[boot] settings/notification failed', e);
      }

      try {
        await weeklyTasksApi.materialize();
      } catch (e) {
        console.error('weekly materialize 失敗:', e);
      }

      const hasCache = !!loadCache<Task[]>(TASKS_CACHE_KEY);

      await loadTasks({ silent: hasCache });
      await loadWeeklyTemplates();
      await loadTaskNotificationOverrides();

      // 観測用 ping
      try {
        console.log('[boot] ping notifications/in-app ...');
        await fetchInAppNotifications(1);
        console.log('[boot] ping notifications/in-app OK');
      } catch (e) {
        console.error('[boot] ping notifications/in-app FAILED', e);
      }

      await refreshNotifBadge();
    })();
  }, []);

  useEffect(() => {
    // ✅ HashRouter: "#/dashboard?tab=notifications" から tab を読む
    const hash = location.hash ?? '';
    const qIndex = hash.indexOf('?');
    const query = qIndex >= 0 ? hash.slice(qIndex + 1) : '';
    const sp = new URLSearchParams(query);
    const tab = sp.get('tab');

    // 許可リスト（壊れない）
    const allowed: TabKey[] = ['today', 'all', 'stats', 'weekly', 'add', 'settings', 'notifications'];
    if (tab && allowed.includes(tab as TabKey)) {
      setActiveTab(tab as TabKey);
    }
  }, [location.hash]);

  // 🔔 notifications タブを開いたら通知一覧を取得
  useEffect(() => {
    if (activeTab !== 'notifications') return;
    // ✅ これが出れば「通知タブに入って取得処理が走った」が確定
    console.log('[notifications] loading in-app notifications...');
    let cancelled = false;

    (async () => {
      setNotifsLoading(true);
      setNotifsError(null);
      setLatestRunLoading(true);
      setLatestRunError(null);
      try {
        const [items, run, summary] = await Promise.all([
          fetchInAppNotifications(50),
          fetchLatestNotificationRunApi(),
          fetchInAppNotificationsSummary(),
        ]);

        if (!cancelled) {
          setNotifs(items);
          setLatestRun(run);

          // ✅ 通知タブを開いたら「既読」扱い（消さなくてもバッジ0）
          const inapp = (summary as any)?.inapp;
          const total = Number(inapp?.total ?? 0) || 0;

          setNotifLastSeenTotal(total);
          saveNotifLastSeenTotal(total);
          setNotifBadgeCount(0);
        }
      } catch (e) {
        console.error('通知一覧の取得に失敗しました:', e);
        if (!cancelled) setNotifsError('通知の取得に失敗しました');
        if (!cancelled) setLatestRunError('最新Cronの取得に失敗しました');
      } finally {
        if (!cancelled) setNotifsLoading(false);
        if (!cancelled) setLatestRunLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [activeTab]);

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
        fromDb[r.task_id] = { morning, offsetsHours: offsets.length ? offsets : [1] };
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

  const allDisplayTasks = useMemo(() => {
    const xs = getAllTasksByViewMode(tasks, allViewMode);

    // ✅ 管理中（active）のみ：締切昇順を保証
    if (allViewMode === 'active') {
      return [...xs].sort(
        (a, b) =>
          new Date(a.deadline).getTime() - new Date(b.deadline).getTime()
      );
    }
    return xs;
  }, [tasks, allViewMode]);

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

  // 🔔 通知を消す（UIは先に消して体感を良くする）
  const handleDismissNotif = async (id: number) => {
    const prev = notifs;
    setNotifs(prev.filter((n) => n.id !== id));

    try {
      await dismissInAppNotification(id);
    } catch (e) {
      console.error('通知のdismissに失敗:', e);
      setNotifs(prev);
      alert('通知の削除に失敗しました');
    } finally {
      // ✅ badgeはsummaryがSSOT
      refreshNotifBadge();
    }
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

  // ✅ キャッシュが無い初回だけは全画面ローディング（真っ白防止）
  const hasTasksCache = useMemo(() => {
    const cached = loadCache<Task[]>(TASKS_CACHE_KEY);
    return !!(cached && Array.isArray(cached.data) && cached.data.length >= 0);
  }, []);

  if (isLoading && !hasTasksCache) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center' }}>
        読み込み中...
      </div>
    );
  }

  // メインコンテンツの切り替え
  const renderContent = () => {
    switch (activeTab) {
      case 'notifications':
        return (
          <div style={{ paddingBottom: '4rem' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '0.75rem',
              }}
            >
              <h1 style={{ margin: 0 }}>通知</h1>
              <button
                onClick={async () => {
                  setNotifsLoading(true);
                  setNotifsError(null);
                  setLatestRunLoading(true);
                  setLatestRunError(null);

                  try {
                    const [items, run, summary] = await Promise.all([
                      fetchInAppNotifications(50),
                      fetchLatestNotificationRunApi(),
                      fetchInAppNotificationsSummary(),
                    ]);
                    setNotifs(items);
                    setLatestRun(run);

                    // ✅ 更新した時点でも「今見てる」ので既読化
                    const inapp = (summary as any)?.inapp;
                    const total = Number(inapp?.total ?? 0) || 0;
                    setNotifLastSeenTotal(total);
                    saveNotifLastSeenTotal(total);
                    setNotifBadgeCount(0);
                    setNotifs(items);
                    setLatestRun(run);
                  } catch (e) {
                    console.error('通知の更新に失敗:', e);
                    setNotifsError('通知の更新に失敗しました');
                    setLatestRunError('最新Cronの取得に失敗しました');
                  } finally {
                    setNotifsLoading(false);
                    setLatestRunLoading(false);
                  }
                }}
                style={{
                  padding: '0.5rem 0.75rem',
                  borderRadius: '0.75rem',
                  border: '1px solid rgba(255,255,255,.15)',
                  background: 'rgba(255,255,255,.06)',
                  color: 'white',
                }}
              >
                ↻ 更新
              </button>
            </div>
            {/* 🛠 最新Cron（内部用） */}
            <div
              style={{
                marginBottom: '0.9rem',
                borderRadius: '1rem',
                border: '1px solid rgba(255,255,255,.12)',
                background: 'rgba(255,255,255,.04)',
                padding: '0.85rem',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '0.75rem',
                }}
              >
                <div style={{ fontWeight: 800 }}>
                  🛠 最新Cron（監査）
                </div>

                <button
                  onClick={() => setShowRunDetails((p) => !p)}
                  style={{
                    height: '2.2rem',
                    padding: '0 0.75rem',
                    borderRadius: '0.75rem',
                    border: '1px solid rgba(255,255,255,.15)',
                    background: 'rgba(255,255,255,.06)',
                    color: 'white',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {showRunDetails ? '閉じる' : '開く'}
                </button>
              </div>

              {latestRunLoading && (
                <div style={{ marginTop: '0.6rem', opacity: 0.7 }}>
                  読み込み中...
                </div>
              )}
              {latestRunError && (
                <div style={{ marginTop: '0.6rem', color: '#ff8a8a' }}>
                  {latestRunError}
                </div>
              )}

              {!latestRunLoading && !latestRunError && showRunDetails && latestRun && (
                (() => {
                  const r = latestRun;
                  const decisionCounts: Record<string, number> =
                    (r.stats?.payload?.decision_counts as Record<string, number> | undefined) ?? {};

                  const entries = (Object.entries(decisionCounts) as Array<[string, number]>)
                    .sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0));

                  const isSentKey = (k: string) => k.startsWith('sent:') || k.startsWith('decision.sent:');
                  const isSkippedKey = (k: string) => k.startsWith('skipped:') || k.startsWith('decision.skipped:');

                  const sent = entries.filter(([k]) => isSentKey(k));
                  const skipped = entries.filter(([k]) => isSkippedKey(k));
                  const other = entries.filter(([k]) => !isSentKey(k) && !isSkippedKey(k));

                  const topN = (xs: [string, number][], n: number) =>
                    showAllReasons ? xs : xs.slice(0, n);

                  const Row = ({ k, v }: { k: string; v: number }) => (
                    <div
                      key={k}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        gap: '0.75rem',
                        padding: '0.35rem 0',
                        borderTop: '1px solid rgba(255,255,255,.06)',
                      }}
                    >
                      <div style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: '0.78rem', opacity: 0.9 }}>
                        {k}
                      </div>
                      <div style={{ fontWeight: 800 }}>{v}</div>
                    </div>
                  );

                  return (
                    <div style={{ marginTop: '0.75rem' }}>
                      <div style={{ fontSize: '0.85rem', opacity: 0.85 }}>
                        run_id: <b>{r.id}</b> / status: <b>{r.status}</b>
                      </div>
                      <div style={{ fontSize: '0.8rem', opacity: 0.7, marginTop: '0.25rem' }}>
                        started: {r.started_at ? new Date(r.started_at).toLocaleString() : '-'}
                      </div>

                      <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', marginTop: '0.6rem' }}>
                        {[
                          ['users_processed', r.users_processed],
                          ['due_total', r.due_candidates_total],
                          ['morning_total', r.morning_candidates_total],
                        ].map(([k, v]) => (
                          <div
                            key={String(k)}
                            style={{
                              padding: '0.35rem 0.55rem',
                              borderRadius: '0.75rem',
                              border: '1px solid rgba(255,255,255,.12)',
                              background: 'rgba(255,255,255,.04)',
                              fontSize: '0.78rem',
                            }}
                          >
                            <span style={{ opacity: 0.7 }}>{k}:</span> <b>{v}</b>
                          </div>
                        ))}
                      </div>

                      <div style={{ marginTop: '0.8rem', fontWeight: 800 }}>decision_counts</div>

                      {entries.length === 0 && (
                        <div style={{ marginTop: '0.4rem', opacity: 0.7 }}>
                          （データなし）
                        </div>
                      )}

                      {sent.length > 0 && (
                        <div style={{ marginTop: '0.6rem' }}>
                          <div style={{ fontSize: '0.82rem', fontWeight: 700, opacity: 0.85 }}>
                            ✅ sent
                          </div>
                          {topN(sent, 5).map(([k, v]) => <Row key={k} k={k} v={v} />)}
                        </div>
                      )}

                      {skipped.length > 0 && (
                        <div style={{ marginTop: '0.6rem' }}>
                          <div style={{ fontSize: '0.82rem', fontWeight: 700, opacity: 0.85 }}>
                            ⛔ skipped
                          </div>
                          {topN(skipped, 8).map(([k, v]) => <Row key={k} k={k} v={v} />)}
                        </div>
                      )}

                      {other.length > 0 && (
                        <div style={{ marginTop: '0.6rem' }}>
                          <div style={{ fontSize: '0.82rem', fontWeight: 700, opacity: 0.85 }}>
                            ℹ️ other
                          </div>
                          {topN(other, 5).map(([k, v]) => <Row key={k} k={k} v={v} />)}
                        </div>
                      )}

                      {entries.length > 10 && (
                        <button
                          onClick={() => setShowAllReasons((p) => !p)}
                          style={{
                            marginTop: '0.7rem',
                            width: '100%',
                            padding: '0.55rem 0.75rem',
                            borderRadius: '0.85rem',
                            border: '1px solid rgba(255,255,255,.15)',
                            background: 'rgba(255,255,255,.06)',
                            color: 'white',
                            fontWeight: 700,
                          }}
                        >
                          {showAllReasons ? '上位だけ表示' : 'もっと見る'}
                        </button>
                      )}
                    </div>
                  );
                })()
              )}

              {!latestRunLoading && !latestRunError && showRunDetails && !latestRun && (
                <div style={{ marginTop: '0.6rem', opacity: 0.7 }}>
                  最新Cronはまだありません（未実行 or 権限なし）
                </div>
              )}
            </div>

            {notifsLoading && <p style={{ opacity: 0.7 }}>読み込み中...</p>}
            {notifsError && <p style={{ color: '#ff8a8a' }}>{notifsError}</p>}

            {!notifsLoading && !notifsError && notifs.length === 0 && (
              <p style={{ opacity: 0.7 }}>通知はありません</p>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {notifs.map((n) => (
                <div
                  key={n.id}
                  onClick={() => {
                    // deep_link は "/#/dashboard?tab=today" 形式
                    // HashRouterなので hash を直接いじるのが最小diffで確実
                    window.location.hash = n.deep_link;
                  }}
                  style={{
                    borderRadius: '1rem',
                    border: '1px solid rgba(255,255,255,.12)',
                    background: 'rgba(255,255,255,.04)',
                    padding: '0.9rem',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 700, marginBottom: '0.25rem' }}>
                        {n.title}
                      </div>
                      <div style={{ whiteSpace: 'pre-wrap', opacity: 0.85, lineHeight: 1.35 }}>
                        {formatNotifBodyForUi(n.body)}
                      </div>

                      <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', opacity: 0.6 }}>
                        {new Date(n.created_at).toLocaleString()}
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDismissNotif(n.id);
                      }}
                      style={{
                        height: '2.25rem',
                        padding: '0 0.75rem',
                        borderRadius: '0.75rem',
                        border: '1px solid rgba(255,255,255,.15)',
                        background: 'rgba(255,255,255,.06)',
                        color: 'white',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      消す
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );

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
              taskNotificationOverrides={taskNotifyOptions}
              onTaskNotificationOptionsChange={handleTaskNotifyOptionsChange}
              isPremium={plan !== 'free'}
              globalNotificationsEnabled={globalNotificationsEnabled}
              onRequestUpgrade={() => {
                window.location.hash = '/upgrade';
              }}
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
              isPremium={plan !== 'free'}
              globalNotificationsEnabled={globalNotificationsEnabled}
              onRequestUpgrade={() => {
                window.location.hash = '/upgrade';
              }}
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
            <NotificationSettings
              globalNotificationsEnabled={globalNotificationsEnabled}
              onGlobalNotificationsEnabledChange={(enabled) => {
                // ✅ 即時反映（リロード不要）
                setGlobalNotificationsEnabled(enabled);

                // ✅ localStorageも同期（次回起動でズレない）
                try {
                  const raw = window.localStorage.getItem(NOTIFICATION_STORAGE_KEY);
                  const prev = raw ? (JSON.parse(raw) as StoredNotificationSettings) : null;
                  const next: StoredNotificationSettings = {
                    enableMorning: prev?.enableMorning ?? true,
                    dailyDigestTime: prev?.dailyDigestTime ?? '08:00',
                    reminderOffsetsHours: prev?.reminderOffsetsHours ?? [1],
                    enableWebpush: enabled,
                  };
                  window.localStorage.setItem(NOTIFICATION_STORAGE_KEY, JSON.stringify(next));
                } catch {}
              }}
            />
          </>
        );
      default:
        return null;
    }
  };

  const ALL_MODE_ITEMS: { key: AllViewMode; label: string; desc: string; icon: string }[] = [
    { key: 'active', label: '管理中', desc: '期限内 / 24h以内の期限切れ', icon: '🟦' },
    { key: 'overdue', label: '期限切れ', desc: '期限超過', icon: '⚠️' },
    { key: 'incomplete', label: '期限内', desc: '期限内', icon: '🕒' },
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
      <div
        style={{
          marginBottom: '0.75rem',
          position: 'relative',
          // ✅ open時は親ごと前面へ（スタッキングコンテキスト対策）
          zIndex: open ? 600 : 1,
          // ✅ 子のz-indexを外部に巻き込まれにくくする（iOS/Safari保険）
          isolation: 'isolate',
        }}
        onClick={(e) => e.stopPropagation()}
      >
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
              // ✅ メニュー自体も十分上へ
              zIndex: 610,
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
      className="df-shell"
      style={{
        width: '100%',
        maxWidth: 'clamp(420px, 92vw, 1100px)',
        margin: '0 auto',
        padding: '0.9rem 1rem calc(5.2rem + env(safe-area-inset-bottom))',
        minHeight: '100dvh',
      }}
    >
      {/* ✅ キャッシュ表示中に裏で更新している場合の軽い表示 */}
      {isLoading && (
        <div
          style={{
            marginBottom: '0.6rem',
            padding: '0.55rem 0.75rem',
            borderRadius: 14,
            border: '1px solid rgba(255,255,255,.10)',
            background: 'rgba(255,255,255,.06)',
            color: 'rgba(255,255,255,.82)',
            fontSize: '0.85rem',
          }}
        >
          更新中…
        </div>
      )}
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
          className="df-title"
          style={{
            fontWeight: 700,
            fontSize: '0.95rem',
            letterSpacing: '0.08em',
            color: 'rgba(255,255,255,.82)',
            userSelect: 'none',
          }}
        >
          DueFlow
        </div>
        <div style={{ width: 36 }} />
      </header>

      {renderContent()}

      {/* ➕ フローティングアクションボタン */}
      {(activeTab === 'today' || activeTab === 'all') && (
        <button
          onClick={handleFabClick}
          className="df-fab"
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
        className="df-bottom-nav"
        style={{
          position: 'fixed',
          left: 0,
          right: 0,
          bottom: 0,
          margin: '0 auto',
          width: '100%',
          maxWidth: 'clamp(420px, 92vw, 1100px)',
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
        <TabButton
          label="通知"
          icon="🔔"
          active={activeTab === 'notifications'}
          badgeCount={notifBadgeCount}
          badgeDotOnly={true}
          onClick={() => {
            setNotifBadgeCount(0); // ✅ 体感：押した瞬間に0（失敗時は次回refreshで復帰）
            window.location.hash = '/dashboard?tab=notifications';
            setActiveTab('notifications');
          }}
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
  badgeCount?: number;
  badgeDotOnly?: boolean;
}

const TabButton: React.FC<TabButtonProps> = ({
  label,
  icon,
  active,
  onClick,
  badgeCount,
  badgeDotOnly = false,
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
      <span style={{ position: 'relative', display: 'inline-block', fontSize: '1.2rem' }}>
        {icon}
        {!!badgeCount && badgeCount > 0 && (
          <span
            style={{
              position: 'absolute',
              top: -4,
              right: -8,
              width: badgeDotOnly ? 10 : 18,
              height: badgeDotOnly ? 10 : 18,
              padding: badgeDotOnly ? 0 : '0 6px',
              borderRadius: 999,
              background: '#ff3b30',
              color: '#fff',
              fontSize: 12,
              lineHeight: badgeDotOnly ? '10px' : '18px',
              textAlign: 'center',
              fontWeight: 800,
              boxShadow: '0 2px 10px rgba(0,0,0,0.35)',
              pointerEvents: 'none',
            }}
          >
            {!badgeDotOnly && (badgeCount >= 100 ? '99+' : badgeCount)}
          </span>
        )}
      </span>
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
