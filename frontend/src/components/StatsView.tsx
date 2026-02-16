// frontend/src/components/StatsView.tsx

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { outcomesApi, OutcomeLog } from '../api/outcomes';
import { analyticsOutcomesApi, Bucket, OutcomesByCourseRow, OutcomesSummaryItem, OutcomesByFeatureRow, OutcomesCourseXFeatureRow,} from '../api/analyticsOutcomes';
import { fetchInAppNotificationsSummary, InAppNotificationsSummary } from '../api/notifications';
import { fetchLatestNotificationRun, fetchRunSummary, NotificationRun, RunSummary } from '../api/notificationRuns';
import type { Task, NotificationSetting} from '../types';
import { buildSuggestedActions } from '../analytics/suggestedActions';
import type { SuggestedAction } from '../analytics/suggestedActions';
import { settingsApi } from '../api/settings';
import { analyticsActionsApi, ActionAppliedEvent, ActionEffectivenessItem, ActionEffectivenessByFeatureItem, ActionEffectivenessSnapshotItem,} from '../api/analyticsActions';
import { SnapshotHeader } from './analytics/SnapshotHeader';
import { SnapshotItemsTable } from './analytics/SnapshotItemsTable';

/**
 * StatsView（監査/分析ビュー）:
 * - OutcomeLog: 締切到達時点の結果（行動の真実）
 * - InAppNotification summary: 通知資産 × ユーザー反応（dismiss）
 * - NotificationRun: cron 実行の事実（観測/監査の真実）
 */
interface StatsViewProps {
  tasks: Task[]; // 互換のため残す（今後 outcomes だけにするなら削除OK）
}

// =========================
// ✅ StatsView UI Cache (stale-while-revalidate)
// - SSOTはサーバの資産ログ。ここは「表示最適化」だけ。
// - localStorage に前回の集計結果を保存して即表示し、裏で再取得して差し替える。
// =========================
const STATS_VIEW_CACHE_VERSION = 1;
const STATS_VIEW_CACHE_KEY = `unipa.statsView.cache.v${STATS_VIEW_CACHE_VERSION}`;

type StatsViewCachePayload = {
  version: number;
  saved_at: string; // ISO
  data: {
    logsWeek: OutcomeLog[];
    logsMonth: OutcomeLog[];
    summaryWeek: OutcomesSummaryItem | null;
    summaryMonth: OutcomesSummaryItem | null;

    byCourseWeek: OutcomesByCourseRow[] | null;
    byCourseMonth: OutcomesByCourseRow[] | null;
    byFeatureWeek: OutcomesByFeatureRow[] | null;
    byFeatureMonth: OutcomesByFeatureRow[] | null;

    weeklyNotifSummary: InAppNotificationsSummary | null;
    monthlyNotifSummary: InAppNotificationsSummary | null;

    latestRun: NotificationRun | null;
    latestRunSummary: RunSummary | null;

    courseXWeek: OutcomesCourseXFeatureRow[] | null;
    courseXMonth: OutcomesCourseXFeatureRow[] | null;

    rateSeriesWeek: RatePoint[];
    rateSeriesMonth: RatePoint[];

    currentNotifSetting: NotificationSetting | null;

    // ✅ ここは「表示キャッシュ」。SSOTではない（SSOTはサーバ資産）
    actionEffectivenessWeek: ActionEffectivenessItem[] | null;
    actionEffectivenessMonth: ActionEffectivenessItem[] | null;

    actionEffectivenessByFeatureWeek: ActionEffectivenessByFeatureItem[] | null;
    actionEffectivenessByFeatureMonth: ActionEffectivenessByFeatureItem[] | null;

    actionEffectivenessMetaWeek: { windowDays: number; fetchedAt: string } | null;
    actionEffectivenessMetaMonth: { windowDays: number; fetchedAt: string } | null;
  };
};

function loadStatsViewCache(): StatsViewCachePayload | null {
  try {
    const raw = localStorage.getItem(STATS_VIEW_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StatsViewCachePayload;
    if (!parsed || parsed.version !== STATS_VIEW_CACHE_VERSION) return null;
    if (!parsed.saved_at || !parsed.data) return null;
    return parsed;
  } catch {
    return null;
  }
}

function saveStatsViewCache(payload: StatsViewCachePayload) {
  try {
    localStorage.setItem(STATS_VIEW_CACHE_KEY, JSON.stringify(payload));
  } catch {
    // storage full / blocked は無視（UX最適化なので致命傷にしない）
  }
}

export const StatsView: React.FC<StatsViewProps> = ({ tasks: _tasks }) => {
  const [_logsWeek, setLogsWeek] = useState<OutcomeLog[]>([]);
  const [_logsMonth, setLogsMonth] = useState<OutcomeLog[]>([]);
  const [bucket, setBucket] = useState<Bucket>('week');
  type StatsTab = 'overview' | 'hotspots' | 'improve' | 'audit';
  const [rateSeriesWeek, setRateSeriesWeek] = useState<RatePoint[]>([]);
  const [rateSeriesMonth, setRateSeriesMonth] = useState<RatePoint[]>([]);
  const rateSeriesRef = useRef<{ week: RatePoint[]; month: RatePoint[] }>({ week: [], month: [] });
  // ✅ audit は通常ユーザーに見せない（案A）
  // NOTE: 将来 user.role 等に差し替え可能。まずは ENV で最小diff。
  const isDeveloper = import.meta.env.VITE_ENABLE_AUDIT === 'true';
  const [activeTab, setActiveTab] = useState<StatsTab>('overview');
  useEffect(() => {
    if (!isDeveloper && activeTab === 'audit') {
      setActiveTab('overview');
    }
  }, [isDeveloper, activeTab]);
  const [_summaryWeek, setSummaryWeek] = useState<OutcomesSummaryItem | null>(null);
  const [_summaryMonth, setSummaryMonth] = useState<OutcomesSummaryItem | null>(null);
  const [byCourseWeek, setByCourseWeek] = useState<OutcomesByCourseRow[] | null>(null);
  const [byCourseMonth, setByCourseMonth] = useState<OutcomesByCourseRow[] | null>(null);
  const [byFeatureWeek, setByFeatureWeek] = useState<OutcomesByFeatureRow[] | null>(null);
  const [byFeatureMonth, setByFeatureMonth] = useState<OutcomesByFeatureRow[] | null>(null);
  const [weeklyNotifSummary, setWeeklyNotifSummary] = useState<InAppNotificationsSummary | null>(null);
  const [monthlyNotifSummary, setMonthlyNotifSummary] = useState<InAppNotificationsSummary | null>(null);
  const [latestRun, setLatestRun] = useState<NotificationRun | null>(null);
  const [latestRunSummary, setLatestRunSummary] = useState<RunSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [courseXWeek, setCourseXWeek] = useState<OutcomesCourseXFeatureRow[] | null>(null);
  const [courseXMonth, setCourseXMonth] = useState<OutcomesCourseXFeatureRow[] | null>(null);
  const [selectedCourseHash, setSelectedCourseHash] = useState<string | null>(null);
  const [currentNotifSetting, setCurrentNotifSetting] = useState<NotificationSetting | null>(null);
  const [applySaving, setApplySaving] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);
  const [applyMessage, setApplyMessage] = useState<string | null>(null);
  const [appliedAt, setAppliedAt] = useState<Date | null>(null);
  const [appliedEvents, setAppliedEvents] = useState<ActionAppliedEvent[] | null>(null);
  const [appliedEventsLoading, setAppliedEventsLoading] = useState(false);
  const [appliedEventsError, setAppliedEventsError] = useState<string | null>(null);
  const [beforeAfterLoading, setBeforeAfterLoading] = useState(false);
  const [beforeAfterError, setBeforeAfterError] = useState<string | null>(null);
  const [beforeSummary, setBeforeSummary] = useState<OutcomesSummaryItem | null>(null);
  const [afterSummary, setAfterSummary] = useState<OutcomesSummaryItem | null>(null);
  const [actionEffectiveness, setActionEffectiveness] = useState<Record<Bucket, ActionEffectivenessItem[] | null>>({
    week: null,
    month: null,
  });

  const [actionEffectivenessByFeature, setActionEffectivenessByFeature] =
    useState<Record<Bucket, ActionEffectivenessByFeatureItem[] | null>>({
      week: null,
      month: null,
    });

  const [actionEffectivenessByFeatureError, setActionEffectivenessByFeatureError] =
    useState<string | null>(null);

  const [actionEffectivenessByFeatureLoading, setActionEffectivenessByFeatureLoading] =
    useState(false);

  const [actionEffectivenessLoading, setActionEffectivenessLoading] = useState(false);
  const [actionEffectivenessError, setActionEffectivenessError] = useState<string | null>(null);
  const [actionEffectivenessMeta, setActionEffectivenessMeta] = useState<
    Record<Bucket, { windowDays: number; fetchedAt: Date } | null>
  >({
    week: null,
    month: null,
  });
  const windowDaysOf = (b: Bucket) => (b === 'week' ? 7 : 30);
  const refetchActionEffectiveness = () => {
    setActionEffectiveness(prev => ({ ...prev, [bucket]: null }));
    setActionEffectivenessByFeature(prev => ({ ...prev, [bucket]: null }));
    setActionEffectivenessMeta(prev => ({ ...prev, [bucket]: null }));
  };

const [effectivenessSnapshots, setEffectivenessSnapshots] =
  useState<ActionEffectivenessSnapshotItem[] | null>(null);
const [effectivenessSnapshotsError, setEffectivenessSnapshotsError] =
  useState<string | null>(null);
const [effectivenessSnapshotsLoading, setEffectivenessSnapshotsLoading] =
  useState(false);
const [selectedSnapshotId, setSelectedSnapshotId] = useState<number | null>(null);  

  useEffect(() => {
    let mounted = true;
    (async () => {
      // ✅ キャッシュ戦略：bucket × feature 単位で一度だけ取得（read-only）
      const shouldFetchByFeature = actionEffectivenessByFeature[bucket] === null;
      if (!shouldFetchByFeature) return;

      setActionEffectivenessByFeatureLoading(true);
      setActionEffectivenessByFeatureError(null);
      try {
        const res = await analyticsActionsApi.getEffectivenessByFeature({
          version: 'v1',
          window_days: windowDaysOf(bucket),
          min_total: 5,
          limit_events: 500,
          limit_samples_per_event: 50,
        });
        if (!mounted) return;
        setActionEffectivenessByFeature(prev => ({
          ...prev,
          [bucket]: res.items ?? [],
        }));
      } catch (e: any) {
        if (!mounted) return;
        setActionEffectivenessByFeatureError(
          e?.message ?? 'failed to load effectiveness by feature'
        );
      } finally {
        if (!mounted) return;
        setActionEffectivenessByFeatureLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [bucket, actionEffectivenessByFeature[bucket]]);

  // ✅ UI: キャッシュ即表示 → 裏で再取得（stale-while-revalidate）
  const [refreshing, setRefreshing] = useState(false);
  const [cacheSavedAt, setCacheSavedAt] = useState<Date | null>(null);

  useEffect(() => {
    // 1) まずキャッシュがあれば即表示（待たせない）
    const cached = loadStatsViewCache();
    if (cached?.data) {
      setLogsWeek(cached.data.logsWeek ?? []);
      setLogsMonth(cached.data.logsMonth ?? []);
      setSummaryWeek(cached.data.summaryWeek ?? null);
      setSummaryMonth(cached.data.summaryMonth ?? null);

      setByCourseWeek(cached.data.byCourseWeek ?? null);
      setByCourseMonth(cached.data.byCourseMonth ?? null);
      setByFeatureWeek(cached.data.byFeatureWeek ?? null);
      setByFeatureMonth(cached.data.byFeatureMonth ?? null);

      setWeeklyNotifSummary(cached.data.weeklyNotifSummary ?? null);
      setMonthlyNotifSummary(cached.data.monthlyNotifSummary ?? null);

      setLatestRun(cached.data.latestRun ?? null);
      setLatestRunSummary(cached.data.latestRunSummary ?? null);

      setCourseXWeek(cached.data.courseXWeek ?? null);
      setCourseXMonth(cached.data.courseXMonth ?? null);

      setRateSeriesWeek(Array.isArray(cached.data.rateSeriesWeek) ? cached.data.rateSeriesWeek : []);
      setRateSeriesMonth(Array.isArray(cached.data.rateSeriesMonth) ? cached.data.rateSeriesMonth : []);

      setCurrentNotifSetting(cached.data.currentNotifSetting ?? null);

      setActionEffectiveness((prev) => ({
        ...prev,
        week: cached.data.actionEffectivenessWeek ?? null,
        month: cached.data.actionEffectivenessMonth ?? null,
      }));

      setActionEffectivenessByFeature((prev) => ({
        ...prev,
        week: cached.data.actionEffectivenessByFeatureWeek ?? null,
        month: cached.data.actionEffectivenessByFeatureMonth ?? null,
      }));

      setActionEffectivenessMeta((prev) => ({
        ...prev,
        week: cached.data.actionEffectivenessMetaWeek
          ? { windowDays: cached.data.actionEffectivenessMetaWeek.windowDays, fetchedAt: new Date(cached.data.actionEffectivenessMetaWeek.fetchedAt) }
          : null,
        month: cached.data.actionEffectivenessMetaMonth
          ? { windowDays: cached.data.actionEffectivenessMetaMonth.windowDays, fetchedAt: new Date(cached.data.actionEffectivenessMetaMonth.fetchedAt) }
          : null,
      }));

      setCacheSavedAt(new Date(cached.saved_at));
      setLoading(false); // ✅ ここが肝：キャッシュがあれば即描画
      setRefreshing(true);
    }

    let mounted = true;
    (async () => {
      try {
        // 2) 裏で再取得（SSOT）
        if (!cached) {
          setLoading(true);
        }
        setError(null);

        // まずは全件取得（重くなったら from/to で絞る）
        const run = await fetchLatestNotificationRun().catch(() => null);

        // 期間（deadline基準でbackendへ渡す）
        const now = new Date();
        const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());

        // 今週の月曜 00:00
        const startOfWeek = new Date(startOfToday);
        const day = startOfWeek.getDay(); // Sun=0, Mon=1 ...
        const diffToMonday = (day === 0 ? -6 : 1) - day;
        startOfWeek.setDate(startOfWeek.getDate() + diffToMonday);
        startOfWeek.setHours(0, 0, 0, 0);

        // 次週月曜 00:00（= 今週の終端 / exclusive）
        const endOfWeek = new Date(startOfWeek);
        endOfWeek.setDate(endOfWeek.getDate() + 7);

        const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
        const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0);

        const endOfMonthEnd = new Date(endOfMonth);
        endOfMonthEnd.setHours(23, 59, 59, 999);

        const fromOutcomesWeek = startOfWeek.toISOString();
        const toOutcomesWeek = endOfWeek.toISOString();

        const fromNotifs = fromOutcomesWeek;
        const toNotifs = toOutcomesWeek;

        const fromOutcomesMonth = startOfMonth.toISOString();
        const toOutcomesMonth = endOfMonthEnd.toISOString();

        // ✅ created_at基準の週次サマリ（Backendへ集計を寄せる）
        const fromNotifsMonth = startOfMonth.toISOString();
        const toNotifsMonth = endOfMonthEnd.toISOString();
        const fmtMD = (d: Date) => `${d.getMonth() + 1}/${d.getDate()}`;
        const fmtYM = (d: Date) => `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}`;

        const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate());

        // [from, to) で扱う（toは翌日0:00など）
        const iso = (d: Date) => d.toISOString();

        const buildWeekWindows = () => {
          // ✅ 月曜始まりの「今週」を基準にする（JST想定）
          const start = startOfDay(now); // 今日 00:00
          const day = start.getDay(); // Sun=0, Mon=1...
          const diffToMonday = (day === 0 ? -6 : 1) - day;

          // 今週の月曜 00:00
          const startOfThisWeek = new Date(start);
          startOfThisWeek.setDate(startOfThisWeek.getDate() + diffToMonday);
          startOfThisWeek.setHours(0, 0, 0, 0);

          // 次週月曜 00:00（= 今週の終端 / exclusive）
          const endExclusive0 = new Date(startOfThisWeek);
          endExclusive0.setDate(endExclusive0.getDate() + 7);

          // ✅ 直近6週（各週は [Mon 00:00, next Mon 00:00)）
          return Array.from({ length: 6 }).map((_, idx) => {
            // 古い -> 新しい の順に並べたいので idx=0 が最古
            const k = 5 - idx;

            const endExclusive = new Date(endExclusive0);
            endExclusive.setDate(endExclusive.getDate() - k * 7);

            const from = new Date(endExclusive);
            from.setDate(from.getDate() - 7);

            // 表示上は endExclusive - 1日（= 日曜）までを見せる
            const endInclusive = new Date(endExclusive.getTime() - 1);

            return {
              from,
              to: endExclusive,
              label: fmtMD(endInclusive),
              rangeLabel: `${fmtMD(from)}-${fmtMD(endInclusive)}`, // ✅ 月〜日になる
            };
          });
        };

        const buildMonthWindows = () => {
          // 直近6ヶ月（当月含む）。idx=0が最古
          const base = new Date(now.getFullYear(), now.getMonth(), 1);
          return Array.from({ length: 6 }).map((_, idx) => {
            const m = 5 - idx;
            const from = new Date(base.getFullYear(), base.getMonth() - m, 1);
            const to = new Date(from.getFullYear(), from.getMonth() + 1, 1); // 次月1日 0:00
            return { from, to, label: fmtYM(from) };
          });
        };

        const fetchSeries = async () => {
          // SSOT（analytics/outcomes/summary）を6回ずつ叩いて棒グラフを作る
          const weekWins = buildWeekWindows();
          const monthWins = buildMonthWindows();

          const weekPoints = await Promise.all(
            weekWins.map(async (w) => {
              try {
                const res = await analyticsOutcomesApi.getSummary({
                  bucket: 'week',
                  from: iso(w.from),
                  to: iso(w.to),
                });
                const item = res.items?.[0];
                const rate = item ? toPercent(item.done_rate) : 0;

                return {
                  label: w.label,
                  rangeLabel: w.rangeLabel,
                  rate,
                  total: item?.total ?? 0,
                  done: item?.done ?? 0,
                };
              } catch {
                return { label: w.label, rangeLabel: w.rangeLabel, rate: 0, total: 0, done: 0 };
              }
            })
          );

          const monthPoints = await Promise.all(
            monthWins.map(async (w) => {
              try {
                const res = await analyticsOutcomesApi.getSummary({
                  bucket: 'month',
                  from: iso(w.from),
                  to: iso(w.to),
                });
                const item = res.items?.[0];
                const rate = item ? toPercent(item.done_rate) : 0;
                return { label: w.label, rate, total: item?.total ?? 0, done: item?.done ?? 0 };
              } catch {
                return { label: w.label, rate: 0, total: 0, done: 0 };
              }
            })
          );

          if (!mounted) return;

          // ✅ “計算完了時点” を ref に保存（payload保存がstate順序に依存しないように）
          rateSeriesRef.current = { week: weekPoints, month: monthPoints };

          // ✅ UI表示は即更新
          setRateSeriesWeek(weekPoints);
          setRateSeriesMonth(monthPoints);

          // ✅ 推移だけは「計算完了時点」でキャッシュへ追記（次回即表示）
          try {
            const cur = loadStatsViewCache();
            if (cur?.data) {
              const savedAt = new Date();
              saveStatsViewCache({
                ...cur,
                saved_at: savedAt.toISOString(),
                data: {
                  ...cur.data,
                  rateSeriesWeek: weekPoints,
                  rateSeriesMonth: monthPoints,
                },
              });
              setCacheSavedAt(savedAt);
            }
          } catch {
            // 表示キャッシュなので失敗しても致命にしない
          }
        };

        // ✅ ここが改善ポイント： fetchSeries(12回API)を await せず、他のデータ取得と並行で走らせる
        fetchSeries().catch(() => null);


        const [
          outcomeWeek,
          outcomeMonth,
          weeklySummary,
          monthlySummary,
          runSummary,
          sumW, sumM, byW, byM, featW, featM,
          cxW, cxM,
          notifSetting,
          effItems,
          effByFeatureItems,
        ] = await Promise.all([
          outcomesApi
            .list({ from: fromOutcomesWeek, to: toOutcomesWeek })
            .catch(() => [] as OutcomeLog[]),
          outcomesApi
            .list({ from: fromOutcomesMonth, to: toOutcomesMonth })
            .catch(() => [] as OutcomeLog[]),

          fetchInAppNotificationsSummary({ from: fromNotifs, to: toNotifs }).catch(() => null),
          fetchInAppNotificationsSummary({ from: fromNotifsMonth, to: toNotifsMonth }).catch(() => null),

          run?.id ? fetchRunSummary(run.id).catch(() => null) : Promise.resolve(null),

          analyticsOutcomesApi.getSummary({ bucket: 'week',  from: fromOutcomesWeek,  to: toOutcomesWeek  }).then(x => x.items?.[0] ?? null).catch(() => null),
          analyticsOutcomesApi.getSummary({ bucket: 'month', from: fromOutcomesMonth, to: toOutcomesMonth }).then(x => x.items?.[0] ?? null).catch(() => null),

          analyticsOutcomesApi.getByCourse({ bucket: 'week',  from: fromOutcomesWeek,  to: toOutcomesWeek  }).then(x => x.items).catch(() => null),
          analyticsOutcomesApi.getByCourse({ bucket: 'month', from: fromOutcomesMonth, to: toOutcomesMonth }).then(x => x.items).catch(() => null),

          analyticsOutcomesApi.getMissedByFeature({ version: 'v1', from: fromOutcomesWeek,  to: toOutcomesWeek,  limit: 2000 }).then(x => x.items).catch(() => null),
          analyticsOutcomesApi.getMissedByFeature({ version: 'v1', from: fromOutcomesMonth, to: toOutcomesMonth, limit: 2000 }).then(x => x.items).catch(() => null),

          analyticsOutcomesApi.getCourseXFeature({ version: 'v1', from: fromOutcomesWeek,  to: toOutcomesWeek,  limit: 20000 }).then(x => x.items).catch(() => null),
          analyticsOutcomesApi.getCourseXFeature({ version: 'v1', from: fromOutcomesMonth, to: toOutcomesMonth, limit: 20000 }).then(x => x.items).catch(() => null),

          settingsApi.getNotification().catch(() => null),

          analyticsActionsApi
            .getEffectiveness({ window_days: windowDaysOf(bucket), min_total: 5, limit_events: 500 })
            .then(x => x.items ?? [])
            .catch(() => []),

          analyticsActionsApi
            .getEffectivenessByFeature({
              version: 'v1',
              window_days: windowDaysOf(bucket),
              min_total: 5,
              limit_events: 500,
              limit_samples_per_event: 50,
            })
            .then(x => x.items ?? [])
            .catch(() => []),
        ]);

        // ✅ この取得結果を “ローカルSSOT” として確定させる（stateは非同期なので参照しない）
        const effMetaNow = { windowDays: windowDaysOf(bucket), fetchedAt: new Date() };

        // ✅ bucketに応じて、週/月のどちらへ入れるかを “payload側で確定”
        const effWeek =
          bucket === 'week'
            ? (effItems ?? [])
            : (actionEffectiveness.week ?? (cached?.data?.actionEffectivenessWeek ?? null));

        const effMonth =
          bucket === 'month'
            ? (effItems ?? [])
            : (actionEffectiveness.month ?? (cached?.data?.actionEffectivenessMonth ?? null));

        const effByFeatWeek =
          bucket === 'week'
            ? (effByFeatureItems ?? [])
            : (actionEffectivenessByFeature.week ?? (cached?.data?.actionEffectivenessByFeatureWeek ?? null));

        const effByFeatMonth =
          bucket === 'month'
            ? (effByFeatureItems ?? [])
            : (actionEffectivenessByFeature.month ?? (cached?.data?.actionEffectivenessByFeatureMonth ?? null));

        const effMetaWeek =
          bucket === 'week'
            ? effMetaNow
            : (actionEffectivenessMeta.week
                ? { windowDays: actionEffectivenessMeta.week.windowDays, fetchedAt: actionEffectivenessMeta.week.fetchedAt }
                : (cached?.data?.actionEffectivenessMetaWeek
                    ? { windowDays: cached.data.actionEffectivenessMetaWeek.windowDays, fetchedAt: new Date(cached.data.actionEffectivenessMetaWeek.fetchedAt) }
                    : null));

        const effMetaMonth =
          bucket === 'month'
            ? effMetaNow
            : (actionEffectivenessMeta.month
                ? { windowDays: actionEffectivenessMeta.month.windowDays, fetchedAt: actionEffectivenessMeta.month.fetchedAt }
                : (cached?.data?.actionEffectivenessMetaMonth
                    ? { windowDays: cached.data.actionEffectivenessMetaMonth.windowDays, fetchedAt: new Date(cached.data.actionEffectivenessMetaMonth.fetchedAt) }
                    : null));

        // ✅ 画面stateも更新（UI用）
        setActionEffectiveness((prev) => ({ ...prev, [bucket]: effItems }));
        setActionEffectivenessMeta((prev) => ({ ...prev, [bucket]: effMetaNow }));
        setActionEffectivenessByFeature((prev) => ({ ...prev, [bucket]: effByFeatureItems ?? [] }));

        if (!mounted) return;

        setLogsWeek(outcomeWeek);
        setLogsMonth(outcomeMonth);
        setWeeklyNotifSummary(weeklySummary);
        setMonthlyNotifSummary(monthlySummary);
        setLatestRun(run);
        setLatestRunSummary(runSummary);
        setSummaryWeek(sumW);
        setSummaryMonth(sumM);
        setByCourseWeek(byW);
        setByCourseMonth(byM);
        setByFeatureWeek(featW);
        setByFeatureMonth(featM);
        setCourseXWeek(cxW);
        setCourseXMonth(cxM);
        setCurrentNotifSetting(notifSetting);

        // 3) 再取得結果をキャッシュに保存（UI用）
        const savedAt = new Date();
        const payload: StatsViewCachePayload = {
          version: STATS_VIEW_CACHE_VERSION,
          saved_at: savedAt.toISOString(),
          data: {
            logsWeek: outcomeWeek ?? [],
            logsMonth: outcomeMonth ?? [],
            summaryWeek: sumW ?? null,
            summaryMonth: sumM ?? null,

            byCourseWeek: byW ?? null,
            byCourseMonth: byM ?? null,
            byFeatureWeek: featW ?? null,
            byFeatureMonth: featM ?? null,

            weeklyNotifSummary: weeklySummary ?? null,
            monthlyNotifSummary: monthlySummary ?? null,

            latestRun: run ?? null,
            latestRunSummary: runSummary ?? null,

            courseXWeek: cxW ?? null,
            courseXMonth: cxM ?? null,

            const refWeek = rateSeriesRef.current.week;
            const refMonth = rateSeriesRef.current.month;

            rateSeriesWeek:
              (Array.isArray(refWeek) && refWeek.length > 0)
                ? refWeek
                : ((Array.isArray(rateSeriesWeek) && rateSeriesWeek.length > 0)
                    ? rateSeriesWeek
                    : (Array.isArray(cached?.data?.rateSeriesWeek) ? cached!.data.rateSeriesWeek : [])),

            rateSeriesMonth:
              (Array.isArray(refMonth) && refMonth.length > 0)
                ? refMonth
                : ((Array.isArray(rateSeriesMonth) && rateSeriesMonth.length > 0)
                    ? rateSeriesMonth
                    : (Array.isArray(cached?.data?.rateSeriesMonth) ? cached!.data.rateSeriesMonth : [])),

            currentNotifSetting: notifSetting ?? null,

            actionEffectivenessWeek: effWeek ?? null,
            actionEffectivenessMonth: effMonth ?? null,

            actionEffectivenessByFeatureWeek: effByFeatWeek ?? null,
            actionEffectivenessByFeatureMonth: effByFeatMonth ?? null,

            actionEffectivenessMetaWeek: effMetaWeek
              ? { windowDays: effMetaWeek.windowDays, fetchedAt: effMetaWeek.fetchedAt.toISOString() }
              : null,
            actionEffectivenessMetaMonth: effMetaMonth
              ? { windowDays: effMetaMonth.windowDays, fetchedAt: effMetaMonth.fetchedAt.toISOString() }
              : null,
          },
        };
        saveStatsViewCache(payload);
        setCacheSavedAt(savedAt);
      } catch (e: any) {
        if (!mounted) return;
        // キャッシュ表示がある場合は「致命エラーで真っ白」にしない（UX）
        if (!cached) {
          setError(e?.message ?? 'failed to load outcomes');
        }
      } finally {
        if (!mounted) return;
        setLoading(false);
        setRefreshing(false);
      }
    })();

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    (async () => {
      setEffectivenessSnapshotsLoading(true);
      setEffectivenessSnapshotsError(null);

      try {
        const res = await analyticsActionsApi.getEffectivenessSnapshots({
          bucket,   // ✅ 週/月に連動
          limit: 10 // ✅ 最新10件
        });
        if (!mounted) return;

        const items = Array.isArray(res?.items) ? res.items : [];
        const sorted = [...items].sort((a, b) => {
          const at = new Date(a.computed_at).getTime();
          const bt = new Date(b.computed_at).getTime();
          return bt - at; // computed_at desc
        });

        setEffectivenessSnapshots(sorted);

        // ✅ 選択IDが未設定 or 一覧に存在しない場合は「最新」を選択（sorted[0]）
        setSelectedSnapshotId((prev) => {
          if (sorted.length === 0) return null;
          const exists = prev != null && sorted.some((s) => s.id === prev);
          return exists ? prev : sorted[0].id;
        });
      } catch (e: any) {
        if (!mounted) return;
        setEffectivenessSnapshotsError(
          e?.message ?? 'failed to load effectiveness snapshots'
        );
      } finally {
        if (!mounted) return;
        setEffectivenessSnapshotsLoading(false);
      }
    })();

    return () => {
      mounted = false;
    };
    // ✅ bucket変更 or apply後に取得し直す（再計算ではなく資産の再取得）
  }, [bucket, appliedAt]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      // ✅ キャッシュ戦略：bucket 単位で一度だけ取得（read-only）
      // - 再取得したい場合は state を明示的に null に戻す
      const current = actionEffectiveness?.[bucket];
      const shouldFetchEffectiveness = current == null; // null/undefined を両方「未取得」と扱う
      if (!shouldFetchEffectiveness) return;
      setActionEffectivenessLoading(true);
      setActionEffectivenessError(null);
      try {
        const eff = await analyticsActionsApi.getEffectiveness({ window_days: windowDaysOf(bucket), min_total: 5, limit_events: 500 });
        if (!mounted) return;
        setActionEffectiveness((prev) => ({
          ...prev,
          [bucket]: Array.isArray(eff?.items) ? eff.items : [],
        }));
      } catch (e: any) {
        if (!mounted) return;
        setActionEffectivenessError(e?.message ?? 'failed to load effectiveness');
      } finally {
        if (!mounted) return;
        setActionEffectivenessLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [bucket, actionEffectiveness?.[bucket]]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      setAppliedEventsLoading(true);
      setAppliedEventsError(null);
      try {
        const res = await analyticsActionsApi.listApplied({
          bucket,
          limit: 20,
        });
        if (!mounted) return;
        setAppliedEvents(Array.isArray(res?.items) ? res.items : []);
      } catch (e: any) {
        if (!mounted) return;
        setAppliedEventsError(e?.message ?? 'failed to load applied events');
      } finally {
        if (!mounted) return;
        setAppliedEventsLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [bucket, appliedAt]);

  const chosenByCourse = bucket === 'week' ? byCourseWeek : byCourseMonth;
  const chosenByFeature = bucket === 'week' ? byFeatureWeek : byFeatureMonth;
  const chosenCourseX = bucket === 'week' ? courseXWeek : courseXMonth;
  const ratePoints: RatePoint[] = bucket === 'week' ? rateSeriesWeek : rateSeriesMonth;

  const chosenActionEffectiveness = actionEffectiveness[bucket] ?? [];

  const sortedActionEffectiveness = useMemo(() => {
  const xs = chosenActionEffectiveness ?? [];
    return [...xs].sort((a, b) => {
      const ar = Number(a.improved_rate ?? 0);
      const br = Number(b.improved_rate ?? 0);
      // improved_rate desc → 同率なら measured_count desc
      if (br !== ar) return br - ar;
      return Number(b.measured_count ?? 0) - Number(a.measured_count ?? 0);
    });
  }, [chosenActionEffectiveness]);

  // ✅ Priority 7-C: action_id -> 「最も効いてる条件(by-feature)」を引く（表示だけ）
  const bestByFeatureForAction = useMemo(() => {
    const rows = actionEffectivenessByFeature[bucket] ?? [];
    const m = new Map<string, ActionEffectivenessByFeatureItem>();

    for (const r of rows) {
      const prev = m.get(r.action_id);
      if (!prev) {
        m.set(r.action_id, r);
        continue;
      }
      // improved_rate desc → 同率なら total_events desc（表示用）
      const ar = Number(r.improved_rate ?? 0);
      const br = Number(prev.improved_rate ?? 0);
      if (ar !== br) {
        if (ar > br) m.set(r.action_id, r);
      } else {
        if (Number(r.total_events ?? 0) > Number(prev.total_events ?? 0)) m.set(r.action_id, r);
      }
    }
    return m;
  }, [bucket, actionEffectivenessByFeature]);

  const courseHashList = useMemo(() => {
    const xs = chosenCourseX ?? [];
    const s = new Set<string>();
    for (const r of xs) s.add(r.course_hash);
    return Array.from(s);
  }, [chosenCourseX]);

  const courseTotals = useMemo(() => {
    const xs = chosenCourseX ?? [];
    const m = new Map<string, { total: number; missed: number }>();
    for (const r of xs) {
      const cur = m.get(r.course_hash) ?? { total: 0, missed: 0 };
      cur.total += r.total;
      cur.missed += r.missed;
      m.set(r.course_hash, cur);
    }
    return m;
  }, [chosenCourseX]);

  const worstCourseHash = useMemo(() => {
    let best: { ch: string; rate: number } | null = null;
    for (const [ch, c] of courseTotals.entries()) {
      const rate = c.total > 0 ? c.missed / c.total : 0;
      if (!best || rate > best.rate) best = { ch, rate };
    }
    return best?.ch ?? null;
  }, [courseTotals]);

  useEffect(() => {
    if (selectedCourseHash) return;
    if (worstCourseHash) setSelectedCourseHash(worstCourseHash);
    else if (courseHashList[0]) setSelectedCourseHash(courseHashList[0]);
  }, [selectedCourseHash, worstCourseHash, courseHashList]);

  const reasons = useMemo(() => {
    if (!chosenCourseX || !selectedCourseHash) return [];
    return [...chosenCourseX]
      .filter((r) => r.course_hash === selectedCourseHash)
      .sort((a, b) => toPercent(b.missed_rate) - toPercent(a.missed_rate))
      .slice(0, 5);
  }, [chosenCourseX, selectedCourseHash]);

  const applySuggestedAction = async (a: SuggestedAction) => {
    const patch = a.patch;
    if (!patch) {
      setApplyError(null);
      setApplyMessage('これは手動アクションです（設定の自動適用はありません）');
      return;
    }
    setApplyError(null);
    setApplySaving(true);
    try {
      await settingsApi.updateNotification(patch);
      const refreshed = await settingsApi.getNotification().catch(() => null);
      if (refreshed) setCurrentNotifSetting(refreshed);

      // ✅ 適用イベントを資産として記録（OutcomeLogとは別レイヤ）
      await analyticsActionsApi.recordApplied({
        action_id: a.id,
        bucket,
        applied_at: new Date().toISOString(),
        payload: {
          patch: patch,
          reason_keys: a.reason_keys ?? [],
        },
      }).catch(() => null);
      setApplyMessage('通知設定に提案を適用しました');
      setAppliedAt(new Date());
    } catch (e: any) {
      setApplyError(e?.message ?? 'failed to apply');
      setApplyMessage('提案の適用に失敗しました');
    } finally {
      setApplySaving(false);
    }
  };

  const evidenceForAction = (a: SuggestedAction, rows: OutcomesCourseXFeatureRow[]) => {
    const keys = a.reason_keys ?? [];
    if (keys.length === 0) return [];

    return [...rows]
      .filter((r) => keys.includes(r.feature_key))
      .sort((x, y) => toPercent(y.missed_rate) - toPercent(x.missed_rate))
      .slice(0, 3);
  };

  const suggestedActions = useMemo(() => {
    if (!reasons || reasons.length === 0) return [];
    return buildSuggestedActions(reasons, currentNotifSetting);
  }, [reasons, currentNotifSetting]);

  // ✅ Priority 3-D: 適用前/後の達成率を比較（read-only）
  useEffect(() => {
    let mounted = true;
    (async () => {
      if (!appliedAt) return;
      setBeforeAfterError(null);
      setBeforeAfterLoading(true);
      try {
        const { before, after } = buildBeforeAfterRange(appliedAt, bucket);
        const [b, a] = await Promise.all([
          analyticsOutcomesApi
            .getSummary({ bucket, from: before.from, to: before.to })
            .then((x) => x.items?.[0] ?? null)
            .catch(() => null),
          analyticsOutcomesApi
            .getSummary({ bucket, from: after.from, to: after.to })
            .then((x) => x.items?.[0] ?? null)
            .catch(() => null),
        ]);
        if (!mounted) return;
        setBeforeSummary(b);
        setAfterSummary(a);
      } catch (e: any) {
        if (!mounted) return;
        setBeforeAfterError(e?.message ?? 'failed to load before/after');
      } finally {
        if (!mounted) return;
        setBeforeAfterLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [appliedAt, bucket]);

  // ✅ 表示用にソート（missed_rate desc）
  const sortedByFeature = useMemo(() => {
    if (!chosenByFeature) return null;
    return [...chosenByFeature].sort((a, b) => toPercent(b.missed_rate) - toPercent(a.missed_rate));
  }, [chosenByFeature]);

  const hotspotSorted = useMemo(() => {
    if (!sortedByFeature) return null;
    return sortedByFeature.filter(
      (r) => r.feature_key === 'deadline_dow_jst' || r.feature_key === 'deadline_hour_jst'
    );
  }, [sortedByFeature]);

  const hotspotDow = hotspotSorted
    ? hotspotSorted.filter((r) => r.feature_key === 'deadline_dow_jst').slice(0, 3)
    : [];

  const hotspotHour = hotspotSorted
    ? hotspotSorted.filter((r) => r.feature_key === 'deadline_hour_jst').slice(0, 3)
    : [];


  // ✅ feature_key を日本語に（未知キーはそのまま表示）
  const labelFeatureKey = (k: string) => {
    const m: Record<string, string> = {
      deadline_is_weekend: '週末締切',
      deadline_dow_jst: '締切の曜日（JST）',
      deadline_hour_jst: '締切の時刻（JST）',
      title_len_bucket: 'タイトル長',
      has_memo: 'メモあり',
      is_weekly_task: '週次タスク由来',
    };
    return m[k] ?? k;
  };

  const stabilityBadge = (measured: number | null | undefined) => {
    const m = Number(measured ?? 0);
    if (m < 10) return { label: '⚠️ 不安定', hint: '計測数が少ないためブレやすい' };
    if (m < 30) return { label: '△ やや不安定', hint: 'もう少し計測が欲しい' };
    return { label: '✅ 安定', hint: '十分な計測があり比較的信頼できる' };
  };

  const isRecommendedAction = (x: {
    improved_rate?: number | null;
    measured_count?: number | null;
  }) => {
    const improved = Number(x.improved_rate ?? 0);
    const measured = Number(x.measured_count ?? 0);
    return improved >= 0.05 && measured >= 30; // 5%以上 & 安定
  };

  const isCautionAction = (x: {
    improved_rate?: number | null;
    measured_count?: number | null;
  }) => {
    const improved = Number(x.improved_rate ?? 0);
    const measured = Number(x.measured_count ?? 0);

    // 改善率は高いが、サンプル不足
    return improved >= 0.05 && measured < 10;
  };

  const hypothesisForAction = (actionId: string) => {
    // ① 既知actionはテンプレで“意味を固定”
    const known: Record<string, string> = {
      weekend_enable_morning: '週末締切が多い人は「朝通知ON」で着手が増えてmissedが減る可能性',
      latenight_enable_webpush_and_1h: '深夜締切が多い人は「WebPush+1時間前」で見落としが減る可能性',
      add_memo: 'メモを1行足すと「やること」が明確になり完了率が上がる可能性',
      generic: '基本は「1時間前通知」で取りこぼしが減る可能性',
    };
    if (known[actionId]) return known[actionId];

    // ② 未知actionは、by-feature の最強条件から仮説を作る（拡張耐性）
    const bf = bestByFeatureForAction.get(actionId);
    if (!bf) return null;

    return `「${labelFeatureKey(bf.feature_key)}=${labelFeatureValue(bf.feature_value, bf.feature_key)}」条件で効果が出やすい可能性`;
  };

  const labelFeatureValue = (v: OutcomesByFeatureRow['feature_value'], key?: string) => {
    if (v == null) return '—';

    if (key === 'deadline_dow_jst') {
      const n = Number(v);
      const days = ['月', '火', '水', '木', '金', '土', '日'];
      return Number.isFinite(n) && n >= 0 && n <= 6 ? days[n] : String(v);
    }

    if (key === 'deadline_hour_jst') {
      if (v == null) return '—';

      // "22:30" 形式
      if (typeof v === 'string' && v.includes(':')) {
        return v;
      }

      const n = Number(v);
      if (!Number.isFinite(n)) return String(v);

      const hour = Math.floor(n);
      const minutes = Math.round((n - hour) * 60);

      if (minutes === 0) return `${hour}:00`;
      if (minutes === 30) return `${hour}:30`;

      // 想定外でも壊れないようにフォールバック
      return `${hour}:${String(minutes).padStart(2, '0')}`;
    }

    if (typeof v === 'boolean') return v ? 'Yes' : 'No';
    return String(v);
  };

  function toPercent(v: number | null | undefined) {
    if (v == null) return 0;
    const n = Number(v);
    if (!Number.isFinite(n)) return 0;
    return n <= 1 ? Math.round(n * 100) : Math.round(n);
  }

  const missedRateOf = (s: OutcomesSummaryItem | null) => {
    if (!s) return 0;
    const total = Number(s.total ?? 0);
    const missed = Number(s.missed ?? 0);
    if (!Number.isFinite(total) || total <= 0) return 0;
    return Math.round((missed / total) * 100);
  };

  // appliedAt を境に「同じ長さ」の before/after を作る（week=7d, month=30d）
  function buildBeforeAfterRange(dt: Date, b: Bucket) {
    const windowDays = b === 'week' ? 7 : 30;
    const ms = windowDays * 24 * 60 * 60 * 1000;
    const t = dt.getTime();
    const beforeFrom = new Date(t - ms);
    const beforeTo = new Date(t);
    const afterFrom = new Date(t);
    // after は「今」までに丸める（未来を取りに行かない）
    const afterTo = new Date(Math.min(Date.now(), t + ms));
    return {
      before: { from: beforeFrom.toISOString(), to: beforeTo.toISOString() },
      after: { from: afterFrom.toISOString(), to: afterTo.toISOString() },
    };
  }

  const courseKeyOf = (r: OutcomesByCourseRow) =>
    r.course_name || r.course_key || r.course_hash || 'unknown';

  const labelCourse = (raw: string) => {
    if (!raw) return 'unknown';
    // hash っぽい値でも見やすく短縮（表示だけ。仕様変更ではない）
    return raw.length > 16 ? `${raw.slice(0, 8)}…${raw.slice(-4)}` : raw;
  };

  const chosenNotifSummary =
    bucket === 'week' ? weeklyNotifSummary : monthlyNotifSummary;

  // ✅ 表示用にソート（backendの並びに依存しない）
  const sortedByCourse = useMemo(() => {
    if (!chosenByCourse) return null;
    return [...chosenByCourse].sort((a, b) => toPercent(b.missed_rate) - toPercent(a.missed_rate));
  }, [chosenByCourse]);

  const worstCourse = sortedByCourse?.[0] ?? null;

  type TabLayer = 'metrics' | 'insights' | 'actions' | 'audit';

  const tabs = useMemo(() => ([
    { key: 'overview' as const, label: '全体', layer: 'metrics' as TabLayer },
    { key: 'hotspots' as const, label: '要注意パターン', layer: 'insights' as TabLayer },
    { key: 'improve' as const, label: '改善点', layer: 'actions' as TabLayer },
    ...(isDeveloper ? ([{ key: 'audit' as const, label: 'audit', layer: 'audit' as TabLayer }] as const) : []),
  ] as const), [isDeveloper]);

  if (loading) {
    return <div style={{ color: 'rgba(255,255,255,.7)' }}>Loading…</div>;
  }
  if (error) {
    return <div style={{ color: '#fca5a5' }}>Failed: {error}</div>;
  }
  // =========================
  // Layer: Metrics (facts)
  // =========================
  const MetricsOverview = () => {
    // ✅ NotifStatsCard 用：週/月の WebPush 指標を “ここで確定”（JSX内で計算しない）
    const inappWp = (latestRunSummary as any)?.inapp?.webpush;

    // message軸（最優先：通知メッセージ数）
    const periodSentMessages = Number(inappWp?.sent_messages ?? 0);
    const periodOpenedMessagesRaw = inappWp?.opened_messages;

    // events軸（fallback：通知イベント数）
    const periodSentEvents = Number(chosenNotifSummary?.webpush_events?.sent ?? 0);

    // created（分母）：message軸が取れたらそれ。無ければ event軸。
    const createdForPeriod = periodSentMessages > 0 ? periodSentMessages : periodSentEvents;

    // opened（分子）：message軸が取れた時だけ。0は0で出す。欠損はundefined。
    const openedForPeriod =
      periodOpenedMessagesRaw == null ? undefined : Number(periodOpenedMessagesRaw);

    // open_rate：取れたらそれ。無ければ opened/created（両方揃ってる時だけ）
    const openRateForPeriod = (() => {
      const or = inappWp?.open_rate;
      if (or != null) return Number(or);
      if (createdForPeriod > 0 && openedForPeriod != null) return openedForPeriod / createdForPeriod;
      return undefined;
    })();

    return (
      <>
        {/* ✅ Metricsは「定義固定」：進捗（現在）と確定（Outcome）を分離 */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))',
            gap: '0.9rem',
          }}
        >
          <StatsCard
            title={bucket === 'week' ? '今週の達成率' : '今月の達成率'}
            subtitle="期限内完了率"
            rate={bucket === 'week' ? toPercent(_summaryWeek?.done_rate) : toPercent(_summaryMonth?.done_rate)}
            total={bucket === 'week' ? Number(_summaryWeek?.total ?? 0) : Number(_summaryMonth?.total ?? 0)}
            done={bucket === 'week' ? Number(_summaryWeek?.done ?? 0) : Number(_summaryMonth?.done ?? 0)}
          />
        </div>

        {/* ✅ Overview: 週/通知反応/月/Run を “グリッドで1塊” にする */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))',
            gap: '0.9rem',
          }}
        >
          {/* ✅ RateBars は必ず全幅 */}
          <div style={{ gridColumn: '1 / -1' }}>
            <RateBars points={Array.isArray(ratePoints) ? ratePoints : []} bucket={bucket} />
          </div>

          {/* ✅ 1枚だけのカードは中央寄せ（左右の無駄な隙間を作らない） */}
          <div
            style={{
              gridColumn: '1 / -1',
              display: 'flex',
              justifyContent: 'center',
            }}
          >
            <div style={{ width: 'min(520px, 100%)' }}>
              <NotifStatsCard
                title={bucket === 'week' ? '今週の通知反応' : '今月の通知反応'}
                subtitle={undefined}
                created={createdForPeriod}
                opened={openedForPeriod}
                dismissed={openedForPeriod}     // 互換
                dismissRate={openRateForPeriod} // 互換
              />
            </div>
          </div>
        </div>
      </>
    );
  };

  // =========================
  // Layer: Insights (interpretation)
  // =========================
  const InsightsHotspots = (
    <div
      style={{
        padding: '1rem 1.1rem',
        borderRadius: 18,
        border: '1px solid rgba(255,255,255,.12)',
        background: 'rgba(255,255,255,.04)',
      }}
    >
      <div style={{ fontWeight: 900, marginBottom: '0.4rem' }}>
        要注意パターン
      </div>
      <div style={{ display: 'grid', gap: '0.75rem' }}>
        {/* 曜日 */}
        <div>
          <div style={{ fontWeight: 850, marginBottom: '0.35rem' }}>
            曜日  Top3
          </div>

          {hotspotDow.length === 0 ? (
            <div style={{ opacity: 0.7 }}>（データなし）</div>
          ) : (
            <div style={{ display: 'grid', gap: '0.35rem' }}>
              {hotspotDow.map((r, idx) => (
                <div
                  key={`dow-${idx}-${String(r.feature_value)}`}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    padding: '0.45rem 0.6rem',
                    borderRadius: 12,
                    border: '1px solid rgba(255,255,255,.10)',
                    background: 'rgba(255,255,255,.03)',
                  }}
                >
                  <div style={{ fontWeight: 800 }}>
                    #{idx + 1}{' '}
                    {r.feature_key === 'deadline_hour_jst'
                      ? `${r.feature_value}時`
                      : labelFeatureValue(r.feature_value, r.feature_key)}
                  </div>
                  <div style={{ opacity: 0.82 }}>
                    {toPercent(r.missed_rate)}%（{r.missed}/{r.total}）
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 時間帯 */}
        <div>
          <div style={{ fontWeight: 850, marginBottom: '0.35rem' }}>
            時間帯  Top3
          </div>

          {hotspotHour.length === 0 ? (
            <div style={{ opacity: 0.7 }}>（データなし）</div>
          ) : (
            <div style={{ display: 'grid', gap: '0.35rem' }}>
              {hotspotHour.map((r, idx) => (
                <div
                  key={`hour-${idx}-${String(r.feature_value)}`}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    padding: '0.45rem 0.6rem',
                    borderRadius: 12,
                    border: '1px solid rgba(255,255,255,.10)',
                    background: 'rgba(255,255,255,.03)',
                  }}
                >
                  <div style={{ fontWeight: 800 }}>
                    #{idx + 1}{' '}
                    {labelFeatureValue(r.feature_value, r.feature_key)}
                  </div>
                  <div style={{ opacity: 0.82 }}>
                    {toPercent(r.missed_rate)}%（{r.missed}/{r.total}）
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );

  // =========================
  // Layer: Actions (next steps)
  // =========================
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {(refreshing || cacheSavedAt) && (
        <div
          style={{
            padding: '0.55rem 0.7rem',
            borderRadius: 12,
            border: '1px solid rgba(255,255,255,.12)',
            background: 'rgba(255,255,255,.03)',
            color: 'rgba(255,255,255,.85)',
            fontSize: '0.82rem',
            lineHeight: 1.35,
          }}
        >
          <div style={{ fontWeight: 900 }}>
            {refreshing ? '更新中…（前回の分析を表示しています）' : '分析を表示しました'}
          </div>
          {cacheSavedAt && (
            <div style={{ opacity: 0.75, marginTop: '0.15rem' }}>
              最終更新: {cacheSavedAt.toLocaleString()}
            </div>
          )}
        </div>
      )}

      {/* ✅ Priority 3-A: Outcomes 可視化（read-only） */}
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <button
          onClick={() => setBucket('week')}
          style={{
            flex: 1,
            padding: '0.55rem 0.7rem',
            borderRadius: 14,
            border: '1px solid rgba(255,255,255,.12)',
            background: bucket === 'week' ? 'rgba(0,212,255,.16)' : 'rgba(255,255,255,.06)',
            color: 'rgba(255,255,255,.92)',
            fontWeight: 800,
            cursor: 'pointer',
          }}
        >
          今週
        </button>
        <button
          onClick={() => setBucket('month')}
          style={{
            flex: 1,
            padding: '0.55rem 0.7rem',
            borderRadius: 14,
            border: '1px solid rgba(255,255,255,.12)',
            background: bucket === 'month' ? 'rgba(0,212,255,.16)' : 'rgba(255,255,255,.06)',
            color: 'rgba(255,255,255,.92)',
            fontWeight: 800,
            cursor: 'pointer',
          }}
        >
          今月
        </button>
      </div>
      {/* ✅ Tabs（C-1: ユーザー向け / 監査向けを分離） */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${tabs.length}, minmax(0, 1fr))`,
          gap: '0.5rem',
          marginTop: '0.25rem',
          marginBottom: '0.35rem',
          width: '100%',
        }}
      >
        {tabs.map((t) => {
          const isActive = activeTab === t.key;
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => setActiveTab(t.key)}
              style={{
                padding: '0.4rem 0.65rem',
                borderRadius: 999,
                border: '1px solid rgba(255,255,255,.12)',
                background: isActive ? 'rgba(0,212,255,.16)' : 'rgba(255,255,255,.06)',
                color: 'rgba(255,255,255,.92)',
                fontWeight: 850,
                cursor: 'pointer',
              }}
            >
              {t.label}
            </button>
          );
        })}
      </div>
      {activeTab === 'overview' && <MetricsOverview />}
      {activeTab === 'hotspots' && InsightsHotspots}
      {activeTab === 'improve' && (
        <>
          {/* ✅ C2-3: Next Best Action（最優先 / 固定表示） */}
          <div
            style={{
              padding: '1rem 1.1rem',
              borderRadius: 18,
              border: '1px solid rgba(255,255,255,.12)',
              background:
                'radial-gradient(circle at 20% 0%, rgba(34,197,94,.14), rgba(255,255,255,.06) 45%, rgba(255,255,255,.04))',
              backdropFilter: 'blur(16px)',
              WebkitBackdropFilter: 'blur(16px)',
              boxShadow: '0 14px 40px rgba(0,0,0,.38)',
              color: 'rgba(255,255,255,.92)',
              marginBottom: '0.85rem',
            }}
          >
            <div style={{ fontWeight: 950, marginBottom: '0.25rem' }}>
              次にやること（最優先）
            </div>

            {(!suggestedActions || suggestedActions.length === 0) ? (
              <div style={{ opacity: 0.75 }}>（まだ提案がありません）</div>
            ) : (() => {
              const a = suggestedActions[0];
              const ev = evidenceForAction(a, reasons);
              const hyp = hypothesisForAction(a.id);

              return (
                <div
                  style={{
                    border: '1px solid rgba(255,255,255,.10)',
                    borderRadius: 16,
                    padding: '0.85rem 0.95rem',
                    background: 'rgba(255,255,255,.05)',
                  }}
                >
                  <div style={{ fontWeight: 950, fontSize: '1.02rem' }}>{a.title}</div>

                  {/* ✅ 1行要約（迷わない導線） */}
                  <div style={{ marginTop: '0.35rem', fontSize: '0.86rem', opacity: 0.78 }}>
                    {a.description}
                  </div>

                  {/* ✅ 根拠は details（Top3 + 仮説） */}
                  {((ev && ev.length > 0) || hyp) && (
                    <details style={{ marginTop: '0.65rem' }}>
                      <summary style={{ cursor: 'pointer', fontWeight: 900, opacity: 0.9 }}>
                        根拠（開く）
                      </summary>

                      <div style={{ marginTop: '0.55rem', fontSize: '0.82rem', opacity: 0.86 }}>
                        {hyp && (
                          <div style={{ marginBottom: '0.45rem' }}>
                            <div style={{ fontWeight: 850, opacity: 0.95 }}>仮説</div>
                            <div style={{ opacity: 0.85, marginTop: '0.25rem' }}>{hyp}</div>
                          </div>
                        )}

                        {ev && ev.length > 0 && (
                          <div>
                            <div style={{ fontWeight: 850, opacity: 0.95 }}>根拠（Top3）</div>
                            <div
                              style={{
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '0.25rem',
                                marginTop: '0.25rem',
                              }}
                            >
                              {ev.map((r, idx) => (
                                <div
                                  key={`${a.id}-nba-ev-${r.feature_key}-${String(r.feature_value)}-${idx}`}
                                  style={{ opacity: 0.85 }}
                                >
                                  ・{labelFeatureKey(r.feature_key)} = {labelFeatureValue(r.feature_value, r.feature_key)}
                                  （missed {r.missed}/{r.total} = {toPercent(r.missed_rate)}%）
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* ✅ Proof: 直近1件（Before/After）をコンパクト表示 */}
                        {appliedAt && (
                          <div style={{ marginTop: '0.55rem' }}>
                            <div style={{ fontWeight: 850, opacity: 0.95 }}>直近の効果（Before/After）</div>
                            <div style={{ opacity: 0.85, marginTop: '0.25rem' }}>
                              missed率: {missedRateOf(beforeSummary)}% → {missedRateOf(afterSummary)}%（
                              {(missedRateOf(afterSummary) - missedRateOf(beforeSummary)) >= 0 ? '+' : ''}
                              {missedRateOf(afterSummary) - missedRateOf(beforeSummary)}pt）
                            </div>
                          </div>
                        )}
                      </div>
                    </details>
                  )}

                  {/* ✅ 行動ボタン */}
                  {a.patch ? (
                    <div style={{ marginTop: '0.65rem', display: 'flex', justifyContent: 'flex-end' }}>
                      <button
                        onClick={() => applySuggestedAction(a)}
                        disabled={applySaving || !currentNotifSetting}
                      >
                        {applySaving ? '適用中…' : 'この提案を適用'}
                      </button>
                    </div>
                  ) : (
                    <div style={{ marginTop: '0.65rem', fontSize: '0.8rem', opacity: 0.65 }}>
                      （手動アクション）
                    </div>
                  )}
                </div>
              );
            })()}
          </div>

          {/* ✅ Insights（重い分析はここに畳む） */}
          <details
            style={{
              border: '1px solid rgba(255,255,255,.12)',
              borderRadius: 16,
              background: 'rgba(255,255,255,.04)',
              padding: '0.75rem 0.85rem',
            }}
          >
            <summary
              style={{
                cursor: 'pointer',
                fontWeight: 900,
                color: 'rgba(255,255,255,.92)',
              }}
            >
              詳しい分析
              <span
                style={{
                  marginLeft: 10,
                  fontWeight: 600,
                  fontSize: '0.82rem',
                  opacity: 0.7,
                }}
              >
              </span>
            </summary>

            <div style={{ marginTop: '0.85rem' }}>
              {/* =========================
                  落ちやすい授業（missed率ランキング）
                ========================= */}
              <div
                style={{
                  padding: '1rem 1.1rem',
                  borderRadius: 18,
                  border: '1px solid rgba(255,255,255,.12)',
                  background:
                    'radial-gradient(circle at 20% 0%, rgba(14,165,233,.14), rgba(255,255,255,.06) 45%, rgba(255,255,255,.04))',
                  backdropFilter: 'blur(16px)',
                  WebkitBackdropFilter: 'blur(16px)',
                  boxShadow: '0 14px 40px rgba(0,0,0,.38)',
                  color: 'rgba(255,255,255,.92)',
                }}
              >
                <div style={{ marginBottom: '0.25rem', fontWeight: 900 }}>
                  落としやすいカテゴリ
                </div>

                {!sortedByCourse || sortedByCourse.length === 0 ? (
                  <div style={{ opacity: 0.7 }}>（まだ集計対象がありません）</div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                    {sortedByCourse.slice(0, 3).map((r, idx) => {
                      const key = courseKeyOf(r); // ✅ courseKeyOf を「正式に」使用（未使用エラー解消）
                      const isWorst =
                        worstCourse != null && courseKeyOf(worstCourse) === key; // ✅ worstCourse を「正式に」使用

                      return (
                        <div
                          key={`${key}-${idx}`}
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            gap: '0.75rem',
                            padding: '0.55rem 0.6rem',
                            borderRadius: 12,
                            border: '1px solid rgba(255,255,255,.08)',
                            background: isWorst ? 'rgba(255,70,70,.10)' : 'rgba(255,255,255,.03)',
                          }}
                        >
                          <div style={{ minWidth: 0 }}>
                            <div style={{ fontWeight: 850 }}>
                              #{idx + 1} {labelCourse(key)}
                              {isWorst && (
                                <span style={{ marginLeft: 8, fontSize: '0.75rem', opacity: 0.85 }}>
                                  ← Worst
                                </span>
                              )}
                            </div>
                            <div style={{ fontSize: '0.8rem', opacity: 0.7 }}>
                              missed {r.missed}/{r.total}
                            </div>
                          </div>

                          <div style={{ fontWeight: 900, fontSize: '1.05rem' }}>
                            {toPercent(r.missed_rate)}%
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* 🔻 ここに「授業ランキング表示」の既存コードをそのまま入れてOK */}
                {/* 例: courseRows.map(...) など */}
              </div>

              {/* =========================
                  落ちやすい特徴（feature別 missed率）
                ========================= */}
              <div
                style={{
                  marginTop: '0.9rem',
                  padding: '1rem 1.1rem',
                  borderRadius: 18,
                  border: '1px solid rgba(255,255,255,.12)',
                  background:
                    'radial-gradient(circle at 20% 0%, rgba(168,85,247,.14), rgba(255,255,255,.06) 45%, rgba(255,255,255,.04))',
                  backdropFilter: 'blur(16px)',
                  WebkitBackdropFilter: 'blur(16px)',
                  boxShadow: '0 14px 40px rgba(0,0,0,.38)',
                  color: 'rgba(255,255,255,.92)',
                }}
              >
                <div style={{ marginBottom: '0.25rem', fontWeight: 900 }}>
                  特徴
                </div>

                {!sortedByFeature || sortedByFeature.length === 0 ? (
                  <div style={{ opacity: 0.7 }}>（まだ集計対象がありません）</div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
                    {sortedByFeature.slice(0, 3).map((r, idx) => (
                      <div
                        key={`${r.feature_key}-${String(r.feature_value)}-${idx}`}
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          gap: '0.75rem',
                          padding: '0.55rem 0.6rem',
                          borderRadius: 12,
                          border: '1px solid rgba(255,255,255,.08)',
                          background: 'rgba(255,255,255,.03)',
                        }}
                      >
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontWeight: 850, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                            <span>
                              #{idx + 1} {labelFeatureKey(r.feature_key)} ={' '}
                              {labelFeatureValue(r.feature_value, r.feature_key)}
                            </span>

                            {/* ✅ C2-3: Risk chip（UI分類のみ / SSOT不変） */}
                            {(() => {
                              const p = toPercent(r.missed_rate);
                              const label =
                                p >= 45 ? '高リスク' :
                                p >= 25 ? '注意' :
                                '軽度';

                              const bg =
                                p >= 45 ? 'rgba(255,70,70,.16)' :
                                p >= 25 ? 'rgba(251,191,36,.16)' :
                                'rgba(34,197,94,.14)';

                              const bd =
                                p >= 45 ? 'rgba(255,70,70,.35)' :
                                p >= 25 ? 'rgba(251,191,36,.32)' :
                                'rgba(34,197,94,.30)';

                              return (
                                <span
                                  style={{
                                    fontSize: '0.72rem',
                                    fontWeight: 900,
                                    padding: '0.18rem 0.5rem',
                                    borderRadius: 999,
                                    border: `1px solid ${bd}`,
                                    background: bg,
                                    opacity: 0.95,
                                  }}
                                >
                                  {label}
                                </span>
                              );
                            })()}
                          </div>
                          <div style={{ fontSize: '0.8rem', opacity: 0.7 }}>
                            missed {r.missed}/{r.total}
                          </div>
                        </div>
                        <div style={{ fontWeight: 900, fontSize: '1.05rem' }}>
                          {toPercent(r.missed_rate)}%
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* ✅ Priority 3-C: course × feature（理由表示） */}
                <div
                  style={{
                    marginTop: '0.9rem',
                    padding: '1rem 1.1rem',
                    borderRadius: 18,
                    border: '1px solid rgba(255,255,255,.12)',
                    background:
                      'radial-gradient(circle at 20% 0%, rgba(34,197,94,.14), rgba(255,255,255,.06) 45%, rgba(255,255,255,.04))',
                    backdropFilter: 'blur(16px)',
                    WebkitBackdropFilter: 'blur(16px)',
                    boxShadow: '0 14px 40px rgba(0,0,0,.38)',
                    color: 'rgba(255,255,255,.92)',
                  }}
                >
                  <div style={{ marginBottom: '0.25rem', fontWeight: 900 }}>
                    カテゴリごとの「落ちやすい理由」
                  </div>

                  {courseHashList.length === 0 ? (
                    <div style={{ opacity: 0.7 }}>（まだ集計対象がありません）</div>
                  ) : (
                    <>
                      <div
                        style={{
                          display: 'flex',
                          gap: '0.5rem',
                          alignItems: 'center',
                          marginBottom: '0.65rem',
                        }}
                      >
                        <div style={{ fontSize: '0.85rem', fontWeight: 800, opacity: 0.9 }}>
                          対象授業:
                        </div>

                        <select
                          value={selectedCourseHash ?? ''}
                          onChange={(e) => setSelectedCourseHash(e.target.value || null)}
                          style={{
                            flex: 1,
                            padding: '0.55rem 0.7rem',
                            borderRadius: 14,
                            border: '1px solid rgba(255,255,255,.12)',
                            background: 'rgba(255,255,255,.06)',
                            color: 'rgba(255,255,255,.92)',
                            fontWeight: 800,
                            outline: 'none',
                          }}
                        >
                          {courseHashList.map((ch) => {
                            const c = courseTotals.get(ch) ?? { total: 0, missed: 0 };
                            const rate = c.total > 0 ? Math.round((c.missed / c.total) * 100) : 0;

                            return (
                              <option key={ch} value={ch}>
                                {labelCourse(ch)}（missed {c.missed}/{c.total} = {rate}%）
                              </option>
                            );
                          })}
                        </select>
                      </div>
                      {reasons.length === 0 ? (
                        <div style={{ opacity: 0.7 }}>（この授業の理由データがありません）</div>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
                          {reasons.map((r, idx) => (
                            <div
                              key={`${r.course_hash}-${r.feature_key}-${r.feature_value}-${idx}`}
                              style={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                gap: '0.75rem',
                                padding: '0.5rem 0',
                                borderTop: '1px solid rgba(255,255,255,.08)',
                              }}
                            >
                              <div style={{ minWidth: 0 }}>
                                <div style={{ fontWeight: 800 }}>
                                  #{idx + 1} {labelFeatureKey(r.feature_key)} ={' '}
                                  {labelFeatureValue(r.feature_value, r.feature_key)}
                                </div>
                                <div style={{ fontSize: '0.8rem', opacity: 0.7 }}>
                                  missed {r.missed}/{r.total}
                                </div>
                              </div>
                              <div style={{ fontWeight: 900, fontSize: '1.05rem' }}>
                                {toPercent(r.missed_rate)}%
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                      <div style={{ marginTop: '0.85rem' }}>
                        <div style={{ fontWeight: 900, marginBottom: '0.35rem' }}>
                          おすすめアクション
                        </div>

                        <div style={{ fontSize: '0.8rem', opacity: 0.7, marginBottom: '0.6rem' }}>
                          ※ course×feature の結果から提案（SSOT追加なし）
                        </div>

                        {/* ✅ Priority 3-D: Before/After */}
                        {appliedAt && (
                          <div
                            style={{
                              marginBottom: '0.6rem',
                              padding: '0.7rem 0.85rem',
                              borderRadius: 14,
                              border: '1px solid rgba(255,255,255,.10)',
                              background: 'rgba(255,255,255,.04)',
                            }}
                          >
                            <div style={{ fontWeight: 900, marginBottom: '0.25rem' }}>
                              改善の見える化（Before/After）
                            </div>
                            <div style={{ fontSize: '0.8rem', opacity: 0.7, marginBottom: '0.35rem' }}>
                              適用時刻: {appliedAt.toLocaleString()}
                            </div>

                            {beforeAfterLoading ? (
                              <div style={{ opacity: 0.7 }}>集計中…</div>
                            ) : beforeAfterError ? (
                              <div style={{ color: 'rgba(252,165,165,.9)' }}>failed: {beforeAfterError}</div>
                            ) : (
                              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem' }}>
                                <div style={{ minWidth: 0 }}>
                                  <div style={{ fontWeight: 800, opacity: 0.9 }}>Before</div>
                                  <div style={{ fontSize: '0.85rem', opacity: 0.75 }}>
                                    missed率: {missedRateOf(beforeSummary)}%（{beforeSummary?.missed ?? 0}/{beforeSummary?.total ?? 0}）
                                  </div>
                                </div>

                                <div style={{ minWidth: 0 }}>
                                  <div style={{ fontWeight: 800, opacity: 0.9 }}>After</div>
                                  <div style={{ fontSize: '0.85rem', opacity: 0.75 }}>
                                    missed率: {missedRateOf(afterSummary)}%（{afterSummary?.missed ?? 0}/{afterSummary?.total ?? 0}）
                                  </div>
                                </div>

                                <div style={{ fontWeight: 900, fontSize: '1.05rem' }}>
                                  {missedRateOf(afterSummary) - missedRateOf(beforeSummary) >= 0 ? '+' : ''}
                                  {missedRateOf(afterSummary) - missedRateOf(beforeSummary)}pt
                                </div>
                              </div>
                            )}
                          </div>
                        )}

                        <div
                          style={{
                            marginTop: '0.75rem',
                            padding: '0.7rem 0.85rem',
                            borderRadius: 14,
                            border: '1px solid rgba(255,255,255,.10)',
                            background: 'rgba(255,255,255,.04)',
                          }}
                        >
                          <div style={{ fontWeight: 900, marginBottom: '0.25rem' }}>
                            適用履歴（直近）
                          </div>

                          <div style={{ fontSize: '0.75rem', opacity: 0.65, marginBottom: '0.4rem' }}>
                            analytics/actions/applied（確定資産 / 読み取り専用）
                          </div>

                          {appliedEventsLoading && <div style={{ opacity: 0.7 }}>読み込み中…</div>}

                          {!appliedEventsLoading && appliedEventsError && (
                            <div style={{ color: 'rgba(255,120,120,.95)' }}>{appliedEventsError}</div>
                          )}

                          {!appliedEventsLoading &&
                            !appliedEventsError &&
                            (!appliedEvents || appliedEvents.length === 0) && (
                              <div style={{ opacity: 0.7 }}>（まだ適用履歴がありません）</div>
                            )}

                          {!appliedEventsLoading &&
                            !appliedEventsError &&
                            appliedEvents &&
                            appliedEvents.length > 0 && (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                                {appliedEvents.slice(0, 1).map((e) => (
                                  <div
                                    key={e.id}
                                    style={{
                                      padding: '0.45rem 0.6rem',
                                      borderRadius: 12,
                                      border: '1px solid rgba(255,255,255,.08)',
                                      background: 'rgba(255,255,255,.03)',
                                      fontSize: '0.8rem',
                                    }}
                                  >
                                    <div style={{ fontWeight: 800 }}>{e.action_id}</div>
                                    <div style={{ opacity: 0.75 }}>
                                      applied_at: {new Date(e.applied_at).toLocaleString()}
                                    </div>
                                    {e.payload?.reason_keys?.length > 0 && (
                                      <div style={{ opacity: 0.75 }}>
                                        reason: {e.payload.reason_keys.join(', ')}
                                      </div>
                                    )}
                                  </div>
                                ))}

                                {/* ✅ 履歴（2件目以降）は map の外に出す */}
                                {appliedEvents.length > 1 && (
                                  <details style={{ marginTop: '0.55rem' }}>
                                    <summary style={{ cursor: 'pointer', fontWeight: 850, opacity: 0.9 }}>
                                      履歴（すべて）
                                    </summary>

                                    <div
                                      style={{
                                        marginTop: '0.5rem',
                                        display: 'flex',
                                        flexDirection: 'column',
                                        gap: '0.35rem',
                                      }}
                                    >
                                      {appliedEvents.slice(1).map((e) => (
                                        <div
                                          key={`hist-${e.id}`}
                                          style={{
                                            padding: '0.45rem 0.6rem',
                                            borderRadius: 12,
                                            border: '1px solid rgba(255,255,255,.08)',
                                            background: 'rgba(255,255,255,.03)',
                                            fontSize: '0.8rem',
                                            opacity: 0.9,
                                          }}
                                        >
                                          <div style={{ fontWeight: 800 }}>{e.action_id}</div>
                                          <div style={{ opacity: 0.75 }}>
                                            applied_at: {new Date(e.applied_at).toLocaleString()}
                                          </div>
                                          {e.payload?.reason_keys?.length > 0 && (
                                            <div style={{ opacity: 0.75 }}>
                                              reason: {e.payload.reason_keys.join(', ')}
                                            </div>
                                          )}
                                        </div>
                                      ))}
                                    </div>
                                  </details>
                                )}
                              </div>
                            )}
                        </div>
                        {applyError && (
                          <div
                            style={{
                              color: 'rgba(252,165,165,.9)',
                              fontSize: '0.85rem',
                              marginBottom: '0.5rem',
                            }}
                          >
                            failed: {applyError}
                          </div>
                        )}

                        {applyMessage && (
                          <div style={{ color: 'rgba(187,247,208,.95)', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                            {applyMessage}
                          </div>
                        )}

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                          {suggestedActions.slice(0, 3).map((a) => (
                            <div
                              key={a.id}
                              style={{
                                border: '1px solid rgba(255,255,255,.10)',
                                borderRadius: 14,
                                padding: '0.75rem 0.85rem',
                                background: 'rgba(255,255,255,.05)',
                              }}
                            >
                              <div style={{ fontWeight: 900, marginBottom: '0.25rem' }}>{a.title}</div>

                              {/* ✅ C2-3: 1行要約（迷わない導線） */}
                              <div style={{ fontSize: '0.82rem', opacity: 0.75 }}>
                                {a.description}
                              </div>

                              {/* ✅ C2-3: 根拠は details */}
                              {(() => {
                                const ev = evidenceForAction(a, reasons);
                                const h = hypothesisForAction(a.id);

                                if ((!ev || ev.length === 0) && !h) return null;

                                return (
                                  <details style={{ marginTop: '0.55rem' }}>
                                    <summary style={{ cursor: 'pointer', fontWeight: 850, opacity: 0.9 }}>
                                      根拠（開く）
                                    </summary>

                                    <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', opacity: 0.85 }}>
                                      {h && (
                                        <div style={{ marginBottom: '0.45rem' }}>
                                          <div style={{ fontWeight: 800, opacity: 0.9, marginBottom: '0.2rem' }}>仮説</div>
                                          <div style={{ opacity: 0.85 }}>{h}</div>
                                        </div>
                                      )}

                                      {ev && ev.length > 0 && (
                                        <div>
                                          <div style={{ fontWeight: 800, opacity: 0.9, marginBottom: '0.25rem' }}>根拠（Top3）</div>
                                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                                            {ev.map((r, idx) => (
                                              <div
                                                key={`${a.id}-ev-${r.feature_key}-${String(r.feature_value)}-${idx}`}
                                                style={{ opacity: 0.85 }}
                                              >
                                                ・{labelFeatureKey(r.feature_key)} = {labelFeatureValue(r.feature_value, r.feature_key)}（missed {r.missed}/{r.total} = {toPercent(r.missed_rate)}%）
                                              </div>
                                            ))}
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  </details>
                                );
                              })()}
                              {a.patch ? (
                                <div style={{ marginTop: '0.55rem', display: 'flex', justifyContent: 'flex-end' }}>
                                  <button onClick={() => applySuggestedAction(a)} disabled={applySaving || !currentNotifSetting}>
                                    {applySaving ? '適用中…' : 'この提案を適用'}
                                  </button>
                                </div>
                              ) : (
                                <div style={{ marginTop: '0.55rem', fontSize: '0.8rem', opacity: 0.65 }}>
                                  （手動アクション）
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          </details>
        </>
      )}
      {isDeveloper && activeTab === 'audit' && (

        <>
          {/* ✅ ユーザー向けの要約（最初に目に入る） */}
          <div
            style={{
              marginTop: '0.9rem',
              padding: '0.75rem 0.9rem',
              borderRadius: 14,
              border: '1px solid rgba(255,255,255,.12)',
              background: 'rgba(255,255,255,.03)',
              color: 'rgba(255,255,255,.92)',
            }}
          >
            <div style={{ fontWeight: 900, marginBottom: '0.35rem' }}>
              システム状態
            </div>

            {latestRun ? (
              <div style={{ fontSize: '0.82rem', opacity: 0.82, lineHeight: 1.45 }}>
                <div>
                  最新実行: {new Date((latestRun as any).created_at ?? (latestRun as any).started_at ?? (latestRun as any).startedAt ?? (latestRun as any).createdAt).toLocaleString()}
                </div>
                <div>
                  状態: {String((latestRun as any).status ?? 'unknown')}
                  {'  '} / 通知作成: {Number((latestRunSummary as any)?.inapp?.total ?? 0)}件
                  {'  '} / 既読(閉じた): {Number((latestRunSummary as any)?.inapp?.dismissed_count ?? 0)}件
                </div>
                <div style={{ marginTop: '0.25rem', fontSize: '0.78rem', opacity: 0.68 }}>
                  ※ 詳細は下の「Developer / 監査情報」にあります
                </div>
              </div>
            ) : (
              <div style={{ fontSize: '0.82rem', opacity: 0.75 }}>
                最終実行の情報がありません（まだ実行されていない可能性があります）
              </div>
            )}
          </div>

          {/* ✅ Developer / 監査（詳細） */}
          <details
            style={{
              marginTop: '0.75rem',
              border: '1px solid rgba(255,255,255,.12)',
              borderRadius: 14,
              background: 'rgba(255,255,255,.03)',
              padding: '0.65rem 0.75rem',
            }}
          >
            <summary style={{ cursor: 'pointer', fontWeight: 900, opacity: 0.9 }}>
              Developer / 監査情報
            </summary>

            <div style={{ marginTop: '0.85rem' }}>
              {/* ✅ 1) Snapshot（資産） */}
              <details
                style={{
                  border: '1px solid rgba(255,255,255,.10)',
                  borderRadius: 12,
                  background: 'rgba(255,255,255,.02)',
                  padding: '0.6rem 0.65rem',
                }}
              >
                <summary style={{ cursor: 'pointer', fontWeight: 850, opacity: 0.92 }}>
                  提案効果スナップショット（確定資産）
                </summary>

                <div style={{ marginTop: '0.75rem' }}>
                  <div style={{ fontWeight: 800, marginBottom: '0.35rem' }}>
                    提案効果の確定スナップショット（最新）
                  </div>
                  <div style={{ fontSize: '0.75rem', opacity: 0.65, marginBottom: '0.5rem' }}>
                    analytics/actions/effectiveness/snapshots（確定資産 / 読み取り専用 / 再計算しない）
                  </div>

                  {effectivenessSnapshotsLoading && (
                    <div style={{ fontSize: '0.85rem', opacity: 0.75 }}>
                      snapshot 読み込み中...
                    </div>
                  )}

                  {effectivenessSnapshotsError && (
                    <div style={{ fontSize: '0.85rem', color: 'rgba(255,120,120,.95)' }}>
                      {effectivenessSnapshotsError}
                    </div>
                  )}

                  {!effectivenessSnapshotsError &&
                    (!effectivenessSnapshots || effectivenessSnapshots.length === 0) && (
                      <>
                        <div style={{ opacity: 0.7 }}>
                          （まだ snapshot がありません）
                        </div>
                        <div style={{ marginTop: '0.25rem', fontSize: '0.75rem', opacity: 0.65 }}>
                          ※ 生成には計測イベント数が必要です（min_total / window_days 条件を満たすと作成されます）
                        </div>
                      </>
                    )}

                  {!effectivenessSnapshotsError &&
                    effectivenessSnapshots &&
                    effectivenessSnapshots.length > 0 && (() => {
                      const snap =
                        effectivenessSnapshots.find((s) => s.id === selectedSnapshotId) ??
                        effectivenessSnapshots[0];

                      const sortedSameBucket = [...effectivenessSnapshots]
                        .filter((s) => s.bucket === snap.bucket)
                        .sort(
                          (a, b) =>
                            new Date(b.computed_at).getTime() - new Date(a.computed_at).getTime()
                        );

                      const idx = sortedSameBucket.findIndex((s) => s.id === snap.id);
                      const prevSnap = idx >= 0 ? sortedSameBucket[idx + 1] ?? null : null;

                      const rankMap = (items: ActionEffectivenessItem[]) => {
                        const rows = [...(items ?? [])].sort((a, b) => {
                          const ar = Number(a.improved_rate ?? 0);
                          const br = Number(b.improved_rate ?? 0);
                          if (br !== ar) return br - ar;
                          return Number(b.measured_count ?? 0) - Number(a.measured_count ?? 0);
                        });

                        const m = new Map<string, { rank: number; improved: number; measured: number }>();
                        rows.forEach((x, i) => {
                          m.set(String(x.action_id), {
                            rank: i + 1,
                            improved: Number(x.improved_rate ?? 0),
                            measured: Number(x.measured_count ?? 0),
                          });
                        });
                        return m;
                      };

                      const curRank = rankMap(snap.items);
                      const prevRank = prevSnap ? rankMap(prevSnap.items) : null;

                      const asOfApplied = (() => {
                        if (!appliedEvents || appliedEvents.length === 0) return null;
                        const snapAt = new Date(snap.computed_at).getTime();

                        return (
                          appliedEvents
                            .filter((e) => {
                              const t = new Date(e.applied_at).getTime();
                              return Number.isFinite(t) && t <= snapAt;
                            })
                            .sort(
                              (a, b) =>
                                new Date(b.applied_at).getTime() - new Date(a.applied_at).getTime()
                            )[0] ?? null
                        );
                      })();

                      return (
                        <>
                          <SnapshotHeader
                            snapshots={effectivenessSnapshots}
                            selectedSnapshotId={selectedSnapshotId}
                            onSelect={setSelectedSnapshotId}
                            current={snap}
                            previous={prevSnap}
                            asOfApplied={asOfApplied}
                          />

                          <div
                            style={{
                              padding: '0.7rem 0.85rem',
                              borderRadius: 14,
                              border: '1px solid rgba(255,255,255,.10)',
                              background: 'rgba(255,255,255,.04)',
                              fontSize: '0.85rem',
                            }}
                          >
                          </div>

                          <SnapshotItemsTable
                            snapshotId={snap.id}
                            items={snap.items}
                            currentRankMap={curRank}
                            previousRankMap={prevRank}
                            hasPreviousSnapshot={!!prevSnap}
                          />
                        </>
                      );
                    })()}
                </div>
              </details>

              {/* ✅ 2) 試験（提案の効果） */}
              <details
                style={{
                  marginTop: '0.65rem',
                  border: '1px solid rgba(255,255,255,.10)',
                  borderRadius: 12,
                  background: 'rgba(255,255,255,.02)',
                  padding: '0.6rem 0.65rem',
                }}
              >
                <summary style={{ cursor: 'pointer', fontWeight: 850, opacity: 0.92 }}>
                  提案の効果（試験）
                </summary>

                <div style={{ marginTop: '0.75rem' }}>
                  <div
                    style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      alignItems: 'center',
                      gap: '0.5rem',
                      marginBottom: '0.4rem',
                    }}
                  >
                    <div style={{ fontWeight: 800 }}>
                      提案の効果（試験）
                    </div>
                    <div style={{ fontSize: '0.75rem', opacity: 0.65 }}>
                      安定度: ✅ measured ≥ 30 / △ 10–29 / ⚠️ &lt; 10（計測数ベース）
                    </div>
                    {actionEffectivenessMeta[bucket] && (
                      <div style={{ fontSize: '0.72rem', opacity: 0.65 }}>
                        集計条件: 直近 {actionEffectivenessMeta[bucket]!.windowDays} 日 /
                        再計測時刻: {actionEffectivenessMeta[bucket]!.fetchedAt.toLocaleString()}
                      </div>
                    )}
                    <button
                      onClick={refetchActionEffectiveness}
                      disabled={actionEffectivenessLoading || actionEffectivenessByFeatureLoading}
                      style={{
                        padding: '0.25rem 0.5rem',
                        borderRadius: 10,
                        border: '1px solid rgba(255,255,255,.12)',
                        background: 'rgba(255,255,255,.06)',
                        color: 'rgba(255,255,255,.9)',
                        fontSize: '0.75rem',
                        cursor: 'pointer',
                      }}
                    >
                      再計測
                    </button>
                  </div>

                  <div style={{ fontSize: '0.75rem', opacity: 0.65, marginBottom: '0.5rem' }}>
                    ※ OutcomeLog（締切到達時点の結果）だけで前後比較します。Outcome不足の提案も「行は残り」、measured=0 になります。
                  </div>

                  {actionEffectivenessLoading && (
                    <div style={{ fontSize: '0.85rem', opacity: 0.75 }}>読み込み中...</div>
                  )}
                  {!actionEffectivenessLoading && actionEffectivenessError && (
                    <div style={{ fontSize: '0.85rem', color: 'rgba(255,120,120,.95)' }}>
                      {actionEffectivenessError}
                    </div>
                  )}

                  {!actionEffectivenessLoading && !actionEffectivenessError && (
                    <div style={{ fontSize: '0.85rem', opacity: 0.85 }}>
                      {sortedActionEffectiveness.length === 0 ? (
                        <div>まだデータがありません（適用イベントやOutcomeが貯まると出ます）</div>
                      ) : (
                        <div style={{ display: 'grid', gap: '0.35rem' }}>
                          {sortedActionEffectiveness.slice(0, 8).map((x) => (
                            <div
                              key={x.action_id}
                              style={{
                                padding: '0.55rem 0.65rem',
                                borderRadius: 12,
                                border: '1px solid rgba(255,255,255,.10)',
                                background: 'rgba(255,255,255,.04)',
                              }}
                            >
                              <div style={{ fontWeight: 750 }}>{x.action_id}</div>
                              {(() => {
                                const measured = Number(x.measured_count ?? 0);
                                const b = stabilityBadge(measured);
                                const recommended = isRecommendedAction(x);
                                const caution = isCautionAction(x);
                                const hyp = hypothesisForAction(x.action_id);

                                return (
                                  <>
                                    <div style={{ opacity: 0.8 }}>
                                      improved_rate: {Math.round((Number(x.improved_rate ?? 0) * 100) * 10) / 10}%
                                      {'  '} / measured: {measured}
                                      {'  '} / applied: {Number(x.applied_count ?? 0)}
                                      {'  '} / avgΔmissed: {Number(x.avg_delta_missed_rate ?? 0)}
                                      {'  '} <span title={b.hint}>{b.label}</span>

                                      {recommended && (
                                        <span
                                          style={{
                                            marginLeft: 8,
                                            padding: '0.1rem 0.45rem',
                                            borderRadius: 999,
                                            fontSize: '0.7rem',
                                            fontWeight: 800,
                                            color: 'rgba(0,255,200,.95)',
                                            border: '1px solid rgba(0,255,200,.45)',
                                            background: 'rgba(0,255,200,.08)',
                                          }}
                                          title="改善率が高く、かつ安定しているため今すぐ使う候補"
                                        >
                                          今すぐ使う
                                        </span>
                                      )}

                                      {!recommended && caution && (
                                        <span
                                          style={{
                                            marginLeft: 8,
                                            padding: '0.1rem 0.45rem',
                                            borderRadius: 999,
                                            fontSize: '0.7rem',
                                            fontWeight: 800,
                                            color: 'rgba(255,190,0,.95)',
                                            border: '1px solid rgba(255,190,0,.45)',
                                            background: 'rgba(255,190,0,.08)',
                                          }}
                                          title="改善率は高いが計測数が少ないため、まだ判断しない"
                                        >
                                          ⚠️ まだ信じるな
                                        </span>
                                      )}
                                    </div>

                                    {hyp && (
                                      <div style={{ marginTop: '0.25rem', fontSize: '0.75rem', opacity: 0.72 }}>
                                        仮説: {hyp}
                                      </div>
                                    )}
                                  </>
                                );
                              })()}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </details>

              {/* ✅ 3) 条件別（by-feature） */}
              <details
                style={{
                  marginTop: '0.65rem',
                  border: '1px solid rgba(255,255,255,.10)',
                  borderRadius: 12,
                  background: 'rgba(255,255,255,.02)',
                  padding: '0.6rem 0.65rem',
                }}
              >
                <summary style={{ cursor: 'pointer', fontWeight: 850, opacity: 0.92 }}>
                  提案の効果（条件別）
                </summary>

                <div style={{ marginTop: '0.75rem' }}>
                  <div style={{ fontWeight: 800, marginBottom: '0.35rem' }}>
                    提案の効果（条件別 / by-feature）
                  </div>
                  <div style={{ fontSize: '0.75rem', opacity: 0.65, marginBottom: '0.35rem' }}>
                    安定度: ✅ total ≥ 30 / △ 10–29 / ⚠️ &lt; 10（母数ベース）
                  </div>

                  {actionEffectivenessByFeatureLoading && (
                    <div style={{ fontSize: '0.85rem', opacity: 0.75 }}>読み込み中...</div>
                  )}

                  {!actionEffectivenessByFeatureLoading && actionEffectivenessByFeatureError && (
                    <div style={{ fontSize: '0.85rem', color: 'rgba(255,120,120,.95)' }}>
                      {actionEffectivenessByFeatureError}
                    </div>
                  )}

                  {!actionEffectivenessByFeatureLoading && !actionEffectivenessByFeatureError && (
                    <div style={{ fontSize: '0.85rem', opacity: 0.85 }}>
                      {(actionEffectivenessByFeature[bucket]?.length ?? 0) === 0 ? (
                        <div>まだデータがありません（適用イベントやOutcomeが貯まると出ます）</div>
                      ) : (
                        <div style={{ display: 'grid', gap: '0.35rem' }}>
                          {actionEffectivenessByFeature[bucket]!.slice(0, 8).map((x) => (
                            <div
                              key={`${x.action_id}-${x.feature_key}-${x.feature_value}`}
                              style={{
                                padding: '0.55rem 0.65rem',
                                borderRadius: 12,
                                border: '1px solid rgba(255,255,255,.10)',
                                background: 'rgba(255,255,255,.04)',
                              }}
                            >
                              <div style={{ fontWeight: 750 }}>{x.action_id}</div>
                              {(() => {
                                const measured = Number(x.total_events ?? 0);
                                const b = stabilityBadge(measured);

                                return (
                                  <div style={{ opacity: 0.8 }}>
                                    {labelFeatureKey(x.feature_key)} ={' '}
                                    {labelFeatureValue(x.feature_value, x.feature_key)}
                                    {'  '} / improved_rate:{' '}
                                    {Math.round(Number(x.improved_rate ?? 0) * 1000) / 10}%
                                    {'  '} / improved: {Number(x.improved_events ?? 0)}
                                    {'  '} / total: {measured}
                                    {'  '} <span title={b.hint}>{b.label}</span>
                                  </div>
                                );
                              })()}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </details>
            </div>
          </details>
        </>
      )}
    </div>
  );
};

interface StatsCardProps {
  title: string;
  subtitle?: string; // ✅ optional
  rate: number;
  total: number;
  done: number;
}

const StatsCard: React.FC<StatsCardProps> = ({ title, subtitle, rate, total, done }) => {
  const clampedRate = Math.max(0, Math.min(100, rate));

  // ✅ 近未来（ガラス感）に寄せる
  return (
    <div
      style={{
        padding: '1rem 1.1rem',
        borderRadius: 18,
        border: '1px solid rgba(255,255,255,.12)',
        background:
          'radial-gradient(circle at 20% 0%, rgba(0,212,255,.18), rgba(255,255,255,.06) 45%, rgba(255,255,255,.04))',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        boxShadow: '0 14px 40px rgba(0,0,0,.38)',
        color: 'rgba(255,255,255,.92)',
      }}
    >
      <div style={{ marginBottom: '0.25rem', fontWeight: 800, letterSpacing: '0.02em' }}>
        {title}
      </div>
      {/* ✅ subtitle は「ある時だけ」表示 */}
      {subtitle ? (
        <div style={{ marginBottom: '0.75rem', fontSize: '0.8rem', color: 'rgba(255,255,255,.62)' }}>
          {subtitle}
        </div>
      ) : null}

      <div
        style={{
          position: 'relative',
          height: 16,
          borderRadius: 9999,
          backgroundColor: 'rgba(255,255,255,.10)',
          overflow: 'hidden',
          marginBottom: '0.35rem',
        }}
      >
        <div
          style={{
            width: `${clampedRate}%`,
            height: '100%',
            borderRadius: 9999,
            background: 'linear-gradient(90deg, rgba(34,197,94,.95), rgba(14,165,233,.95))',
            transition: 'width 0.25s ease-out',
          }}
        />
      </div>

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '0.85rem',
          color: 'rgba(255,255,255,.78)',
        }}
      >
        <span>{clampedRate}% 達成</span>
        <span>
          {done} / {total} 件
        </span>
      </div>
    </div>
  );
};

type RatePoint = {
  label: string;       // 表示用（短い）
  rangeLabel?: string; // tooltip用（詳細）
  rate: number;        // 0..100
  done: number;
  total: number;
};

const RateBars: React.FC<{ points: RatePoint[]; bucket: 'week' | 'month' }> = ({
  points,
  bucket,
}) => {
  // ✅ points を必ず配列として扱う（undefined を潰す）
  const safePoints: RatePoint[] = Array.isArray(points) ? points : [];

  const clampPct = (v: any) => Math.max(0, Math.min(100, Number(v ?? 0)));

  // ✅ スマホ判定（<=480px）
  const [isNarrow, setIsNarrow] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 480px)');
    const apply = () => setIsNarrow(mq.matches);
    apply();

    const mqa = mq as any;
    if (typeof mq.addEventListener === 'function') mq.addEventListener('change', apply);
    else if (typeof mqa.addListener === 'function') mqa.addListener(apply);

    return () => {
      if (typeof mq.removeEventListener === 'function') mq.removeEventListener('change', apply);
      else if (typeof mqa.removeListener === 'function') mqa.removeListener(apply);
    };
  }, []);

  // ✅ スマホは4本、PCは6本
  const visibleCount = isNarrow ? 4 : 6;
  const [page, setPage] = useState(0);
  const [pageAnimOn, setPageAnimOn] = useState(true);
  const touchStartXRef = useRef<number | null>(null);
  const touchStartYRef = useRef<number | null>(null);
  const touchLastXRef = useRef<number | null>(null);
  const touchMovedRef = useRef<boolean>(false);

  // ✅ ページ数（最低1）
  const totalPages = Math.max(1, Math.ceil(safePoints.length / visibleCount));

  useEffect(() => {
    setPage(0);
  }, [bucket, safePoints.length, visibleCount]);

  useEffect(() => {
    setPageAnimOn(false);
    const t = window.setTimeout(() => setPageAnimOn(true), 0);
    return () => window.clearTimeout(t);
  }, [page]);

  // 以降 points は safePoints を使う
  const end = Math.max(0, safePoints.length - visibleCount * page);
  const start = Math.max(0, end - visibleCount);
  const rawShown = safePoints.slice(start, end);

  // ✅ pad は「一番古いページ（最後のページ）」だけに限定する
  //    最新ページ(page=0)で pad が混ざるのを禁止（今回のバグの根本）
  const isOldestPage = page === totalPages - 1;

  const shouldPad =
    safePoints.length < visibleCount || (isOldestPage && rawShown.length < visibleCount);

  const padCount = shouldPad ? Math.max(0, visibleCount - rawShown.length) : 0;

  const padPoints: RatePoint[] = Array.from({ length: padCount }).map((_, i) => ({
    label: `__pad_${bucket}_${page}_${i}`, // key衝突防止
    rangeLabel: undefined,
    rate: 0,
    done: 0,
    total: 0,
  }));

  // ✅ 右端＝最新の意味を保つため、左側にpad
  const shownPoints = padCount > 0 ? [...padPoints, ...rawShown] : rawShown;

  const tips = useMemo(() => {
    return shownPoints.map((p) => {
      const isEmpty = !p.total;
      const pct = isEmpty ? 0 : clampPct(p.rate);
      return [
        p.rangeLabel ?? p.label,
        isEmpty ? 'データなし' : `${pct}%（${p.done}/${p.total}）`,
      ].join('\n');
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shownPoints]);

  // ✅ “空なら表示しない” は Hooks の後で（Reactのルールを守る）
  if (safePoints.length === 0) return null;

  // ✅ 前=過去(older) / 次=新しい(newer)
  const canPrev = page < totalPages - 1; // まだ過去がある
  const canNext = page > 0;              // まだ新しい方へ戻れる

  // "2025/12/30-2026/01/05" / "12/30-1/5" / "12/30〜1/5" みたいなのを雑に拾う
  const parseRange = (s?: string | null) => {
    if (!s) return null;

    // 1) YYYY/MM/DD-YYYY/MM/DD
    let m = s.match(
      /(\d{4})\/(\d{1,2})\/(\d{1,2})\s*[-〜~]\s*(\d{4})\/(\d{1,2})\/(\d{1,2})/
    );
    if (m) {
      const start = `${Number(m[2])}/${Number(m[3])}`;
      const end = `${Number(m[5])}/${Number(m[6])}`;
      return { start, end };
    }

    // 2) MM/DD-MM/DD（年なし）
    m = s.match(/(\d{1,2})\/(\d{1,2})\s*[-〜~]\s*(\d{1,2})\/(\d{1,2})/);
    if (m) {
      const start = `${Number(m[1])}/${Number(m[2])}`;
      const end = `${Number(m[3])}/${Number(m[4])}`;
      return { start, end };
    }

    return null;
  };

  const formatBottom = (p: RatePoint) => {
    // ✅ pad のラベルは絶対に見せない
    if ((p.label ?? '').startsWith('__pad_')) return '';

    // 月: "2026/01" -> "1月"
    if (bucket === 'month') {
      const m = (p.label ?? '').match(/^(\d{4})\/(\d{2})$/);
      if (m) return `${Number(m[2])}月`;
      return p.label ?? '';
    }

    const r = parseRange(p.rangeLabel ?? '');
    if (r) return `${r.start}〜`;

    const label = (p.label ?? '').replace(/^(\d{4})\//, '');
    return label;
  };

  return (
    <div style={{ marginTop: '0.85rem', width: '100%' }}>
      {/* ✅ タイトル + ページャ */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '0.75rem',
          marginBottom: '0.55rem',
        }}
      >
        <div style={{ fontSize: '0.85rem', fontWeight: 800, opacity: 0.9 }}>
          達成率の推移
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            type="button"
            onClick={() => canPrev && setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={!canPrev}
            style={{
              padding: '0.25rem 0.5rem',
              borderRadius: 10,
              border: '1px solid rgba(255,255,255,.12)',
              background: canPrev ? 'rgba(255,255,255,.06)' : 'rgba(255,255,255,.03)',
              color: 'rgba(255,255,255,.9)',
              fontSize: '0.8rem',
              fontWeight: 900,
              cursor: canPrev ? 'pointer' : 'not-allowed',
              opacity: canPrev ? 1 : 0.55,
            }}
            aria-label="前の期間"
            title="前の期間"
          >
            ◀
          </button>

          <button
            type="button"
            onClick={() => canNext && setPage((p) => Math.max(0, p - 1))}
            disabled={!canNext}
            style={{
              padding: '0.25rem 0.5rem',
              borderRadius: 10,
              border: '1px solid rgba(255,255,255,.12)',
              background: canNext ? 'rgba(255,255,255,.06)' : 'rgba(255,255,255,.03)',
              color: 'rgba(255,255,255,.9)',
              fontSize: '0.8rem',
              fontWeight: 900,
              cursor: canNext ? 'pointer' : 'not-allowed',
              opacity: canNext ? 1 : 0.55,
            }}
            aria-label="次の期間"
            title="次の期間"
          >
            ▶
          </button>
        </div>
      </div>
      {/* ✅ 表示は “ページ分” のみ */}
      <div
        onTouchStart={(e) => {
          if (!isNarrow) return; // ✅ スマホだけ
          const t = e.touches?.[0];
          if (!t) return;
          touchStartXRef.current = t.clientX;
          touchStartYRef.current = t.clientY;
          touchLastXRef.current = t.clientX;
          touchMovedRef.current = false;
        }}
        onTouchMove={(e) => {
          if (!isNarrow) return;
          const t = e.touches?.[0];
          if (!t) return;
          if (touchStartXRef.current == null || touchStartYRef.current == null) return;
          const dx = t.clientX - touchStartXRef.current;
          const dy = t.clientY - touchStartYRef.current;
          touchLastXRef.current = t.clientX;
          // 縦スクロール優先（横意図のときだけ）
          if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 8) {
            touchMovedRef.current = true;
          }
        }}
        onTouchEnd={() => {
          if (!isNarrow) return;
          if (!touchMovedRef.current) return;
          if (touchStartXRef.current == null || touchLastXRef.current == null) return;

          const dx = touchLastXRef.current - touchStartXRef.current;
          const threshold = 28;
          if (dx <= -threshold) {
            // 👈 左スワイプ = 過去へ（page+1）
            if (canPrev) setPage((p) => Math.min(totalPages - 1, p + 1));
          } else if (dx >= threshold) {
            // 👉 右スワイプ = 最新へ（page-1）
            if (canNext) setPage((p) => Math.max(0, p - 1));
          }
        }}
        style={{
          width: '100%',
          display: 'grid',

          // ✅ ここが主修正： shownPoints.length ではなく「表示本数」で必ず等分
          gridTemplateColumns: `repeat(${visibleCount}, minmax(0, 1fr))`,

          gap: '0.65rem',

          // ✅ iOS/Safari対策：各セルを横幅いっぱいに引き伸ばす
          justifyItems: 'stretch',
          alignItems: 'stretch',

          transition: 'opacity 160ms ease-out, transform 160ms ease-out',
          opacity: pageAnimOn ? 1 : 0,
          transform: pageAnimOn ? 'translateY(0px)' : 'translateY(4px)',
        }}
      >
        {shownPoints.map((p, i) => {
          const isEmpty = !p.total;
          const pct = isEmpty ? 0 : clampPct(p.rate);
          const topText = isEmpty ? '—' : `${pct}%`;
          const bottom = formatBottom(p);

          return (
            <div key={p.label} style={{ minWidth: 0, width: '100%' }}>
              {/* ✅ 上に% */}
              <div
                style={{
                  textAlign: 'center',
                  fontSize: '0.95rem',
                  fontWeight: 900,
                  lineHeight: 1,
                  marginBottom: 8,
                  opacity: isEmpty ? 0.55 : 0.95,
                }}
              >
                {topText}
              </div>

              {/* ✅ バー */}
              <div
                title={tips[i]}
                style={{
                  height: 110,
                  borderRadius: 16,
                  border: '1px solid rgba(255,255,255,.14)',
                  background: 'rgba(255,255,255,.04)',
                  display: 'flex',
                  alignItems: 'flex-end',
                  overflow: 'hidden',
                  opacity: isEmpty ? 0.55 : 1,
                }}
              >
                <div
                  style={{
                    width: '100%',
                    height: `${pct}%`,
                    background: isEmpty ? 'rgba(255,255,255,.08)' : 'rgba(110,231,183,.55)',
                    borderTop: '1px solid rgba(255,255,255,.10)',
                    transition: 'height 0.25s ease-out',
                  }}
                />
              </div>

              {/* ✅ 下：ellipsis を出さないため “左右2分割” + nowrap */}
              <div
                style={{
                  marginTop: 10,
                  display: 'flex',
                  alignItems: 'baseline',
                  justifyContent: 'center',
                  gap: 8,
                  fontSize: '0.78rem',
                  fontWeight: 800,
                  opacity: 0.78,
                  whiteSpace: 'nowrap',
                }}
              >
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {bottom}
                </span>
              </div>

              {/* ✅ (done/total) */}
              <div style={{ marginTop: 2, textAlign: 'center', fontSize: '0.72rem', opacity: 0.65 }}>
                {isEmpty ? '—' : `(${p.done}/${p.total})`}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

interface NotifStatsCardProps {
  title: string;
  subtitle?: string;

  created: number;   // 通知数（分母）
  opened?: number;   // ✅ 開封数（分子）= 通知を押してアプリを開いた数
  // 👇 互換のため残してOK（このカードでは使わない）
  dismissed?: number;
  dismissRate?: number;

  sent?: number;
  failed?: number;
  deactivated?: number;
  sentEvents?: number;
}

const NotifStatsCard: React.FC<NotifStatsCardProps> = (props) => {
  const {
    title,
    subtitle,
    created,
    opened,
    dismissed,
    dismissRate,
  } = props;

  // ✅ 数値化（auditで落ちないためのガード）
  const toNum = (v: any): number => {
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  };

  const createdN = Math.max(0, Math.trunc(toNum(created)));

  // ✅ 互換：opened が来たら opened 優先、無ければ dismissed を使う
  const reactedRaw = opened != null ? opened : dismissed;
  const reactedN0 = Math.max(0, Math.trunc(toNum(reactedRaw)));

  // ✅ reacted は 0..created にクランプ（不整合でもUIは壊さない）
  const reactedN = createdN > 0 ? Math.min(createdN, reactedN0) : 0;

  // ✅ 互換：dismissRate が来たらそれを優先（0-1/0-100 両対応）、無ければ reacted/created
  const normalizePct = (v: any): number | null => {
    if (v == null) return null;
    const n = Number(v);
    if (!Number.isFinite(n)) return null;
    const pct = n <= 1 ? n * 100 : n;
    return Math.max(0, Math.min(100, pct));
  };

  const pctFromProp = normalizePct(dismissRate);
  const reactPct: number | null =
    pctFromProp != null
      ? pctFromProp
      : (createdN > 0 ? Math.max(0, Math.min(100, (reactedN / createdN) * 100)) : null);

  return (
    <div
      style={{
        padding: '1rem 1.1rem',
        borderRadius: 18,
        border: '1px solid rgba(255,255,255,.12)',
        background:
          'radial-gradient(circle at 20% 0%, rgba(168,85,247,.16), rgba(255,255,255,.06) 45%, rgba(255,255,255,.04))',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        boxShadow: '0 14px 40px rgba(0,0,0,.38)',
        color: 'rgba(255,255,255,.92)',
      }}
    >
      <div style={{ marginBottom: '0.25rem', fontWeight: 900, letterSpacing: '0.02em' }}>
        {title}
      </div>

      {subtitle ? (
        <div style={{ marginBottom: '0.75rem', fontSize: '0.8rem', color: 'rgba(255,255,255,.62)' }}>
          {subtitle}
        </div>
      ) : null}

      {/* ✅ 主役：反応率（dismissRate / reacted/created 互換） */}
      <div style={{ marginTop: '0.35rem' }}>
        <div
          style={{
            position: 'relative',
            height: 14,
            borderRadius: 9999,
            backgroundColor: 'rgba(255,255,255,.10)',
            overflow: 'hidden',
            marginBottom: '0.45rem',
          }}
        >
          <div
            style={{
              width: `${reactPct ?? 0}%`,
              height: '100%',
              borderRadius: 9999,
              background: 'linear-gradient(90deg, rgba(168,85,247,.95), rgba(14,165,233,.95))',
              transition: 'width 0.25s ease-out',
            }}
          />
        </div>

        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            gap: '0.75rem',
            fontSize: '0.85rem',
            color: 'rgba(255,255,255,.82)',
            fontWeight: 850,
          }}
        >
          <span>
            <strong>反応率</strong> {reactPct == null ? '—' : `${Math.round(reactPct)}%`}
          </span>
        </div>
      </div>

      {/* ✅ 反応/送信成功 */}
      <div
        style={{
          marginTop: '0.75rem',
          padding: '0.75rem 0.85rem',
          borderRadius: 14,
          border: '1px solid rgba(255,255,255,.10)',
          background: 'rgba(255,255,255,.04)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'baseline',
          gap: 10,
        }}
      >
        <div style={{ fontWeight: 950, fontSize: '1.05rem', letterSpacing: '0.02em' }}>
          {reactedN} / {createdN}
        </div>
      </div>

      {createdN <= 0 ? (
        <div style={{ marginTop: '0.6rem', fontSize: '0.75rem', opacity: 0.65 }}>
          （この期間は通知がありません）
        </div>
      ) : null}
    </div>
  );
};