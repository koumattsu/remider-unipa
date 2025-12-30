// frontend/src/components/StatsView.tsx

import { useEffect, useMemo, useState } from 'react';
import { outcomesApi, OutcomeLog } from '../api/outcomes';
import {
  analyticsOutcomesApi,
  Bucket,
  OutcomesByCourseRow,
  OutcomesSummaryItem,
  OutcomesByFeatureRow,
  OutcomesCourseXFeatureRow,
} from '../api/analyticsOutcomes';
import { fetchInAppNotificationsSummary, InAppNotificationsSummary } from '../api/notifications';
import { fetchLatestNotificationRun, fetchRunSummary, NotificationRun, RunSummary } from '../api/notificationRuns';
import { Task } from '../types';

/**
 * StatsView（監査/分析ビュー）:
 * - OutcomeLog: 締切到達時点の結果（行動の真実）
 * - InAppNotification summary: 通知資産 × ユーザー反応（dismiss）
 * - NotificationRun: cron 実行の事実（観測/監査の真実）
 */
interface StatsViewProps {
  tasks: Task[]; // 互換のため残す（今後 outcomes だけにするなら削除OK）
}

export const StatsView: React.FC<StatsViewProps> = ({ tasks: _tasks }) => {
  const [logs, setLogs] = useState<OutcomeLog[]>([]);
  const [bucket, setBucket] = useState<Bucket>('week');
  const [summaryWeek, setSummaryWeek] = useState<OutcomesSummaryItem | null>(null);
  const [summaryMonth, setSummaryMonth] = useState<OutcomesSummaryItem | null>(null);
  const [byCourseWeek, setByCourseWeek] = useState<OutcomesByCourseRow[] | null>(null);
  const [byCourseMonth, setByCourseMonth] = useState<OutcomesByCourseRow[] | null>(null);
  const [byFeatureWeek, setByFeatureWeek] = useState<OutcomesByFeatureRow[] | null>(null);
  const [byFeatureMonth, setByFeatureMonth] = useState<OutcomesByFeatureRow[] | null>(null);
  const [weeklyNotifSummary, setWeeklyNotifSummary] = useState<InAppNotificationsSummary | null>(null);
  const [latestRun, setLatestRun] = useState<NotificationRun | null>(null);
  const [latestRunSummary, setLatestRunSummary] = useState<RunSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [courseXWeek, setCourseXWeek] = useState<OutcomesCourseXFeatureRow[] | null>(null);
  const [courseXMonth, setCourseXMonth] = useState<OutcomesCourseXFeatureRow[] | null>(null);
  const [selectedCourseHash, setSelectedCourseHash] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        setLoading(true);
        setError(null);
        // まずは全件取得（重くなったら from/to で絞る）
        const run = await fetchLatestNotificationRun().catch(() => null);
        // 期間（deadline基準でbackendへ渡す）
        const now = new Date();
        const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const startOfWeek = new Date(startOfToday);
        startOfWeek.setDate(startOfWeek.getDate() - 6);
        const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
        const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0);

        const endOfToday = new Date(startOfToday);
        endOfToday.setDate(endOfToday.getDate() + 1);

        const endOfMonthEnd = new Date(endOfMonth);
        endOfMonthEnd.setHours(23, 59, 59, 999);

        // ✅ analytics 用（deadline基準）
        const fromOutcomesWeek = startOfWeek.toISOString();
        const toOutcomesWeek = endOfToday.toISOString();

        const fromOutcomesMonth = startOfMonth.toISOString();
        const toOutcomesMonth = endOfMonthEnd.toISOString();

        // ✅ created_at基準の週次サマリ（Backendへ集計を寄せる）
        const fromNotifs = startOfWeek.toISOString();
        const toNotifs = endOfToday.toISOString();

        const [outcomeData, weeklySummary, runSummary, sumW, sumM, byW, byM, featW, featM, cxW, cxM] = await Promise.all([
          // フォールバック用（既存挙動）
          outcomesApi.list({ from: fromOutcomesWeek, to: toOutcomesWeek }),

          // 既存（通知反応）
          fetchInAppNotificationsSummary({ from: fromNotifs, to: toNotifs }),

          // 既存（run summary）
          run?.id ? fetchRunSummary(run.id).catch(() => null) : Promise.resolve(null),

          analyticsOutcomesApi
            .getSummary({ bucket: 'week', from: fromOutcomesWeek, to: toOutcomesWeek })
            .then((x) => x.items?.[0] ?? null)
            .catch(() => null),
          analyticsOutcomesApi
            .getSummary({ bucket: 'month', from: fromOutcomesMonth, to: toOutcomesMonth })
            .then((x) => x.items?.[0] ?? null)
            .catch(() => null),

          analyticsOutcomesApi
            .getByCourse({ bucket: 'week', from: fromOutcomesWeek, to: toOutcomesWeek })
            .then((x) => x.items)
            .catch(() => null),
          analyticsOutcomesApi
            .getByCourse({ bucket: 'month', from: fromOutcomesMonth, to: toOutcomesMonth })
            .then((x) => x.items)
            .catch(() => null),

          analyticsOutcomesApi
            .getMissedByFeature({ version: 'v1', from: fromOutcomesWeek, to: toOutcomesWeek, limit: 2000 })
            .then((x) => x.items)
            .catch(() => null),
          analyticsOutcomesApi
            .getMissedByFeature({ version: 'v1', from: fromOutcomesMonth, to: toOutcomesMonth, limit: 2000 })
            .then((x) => x.items)
            .catch(() => null),

          // ✅ Priority 3-C: course × feature
          analyticsOutcomesApi
            .getCourseXFeature({ version: 'v1', from: fromOutcomesWeek, to: toOutcomesWeek, limit: 20000 })
            .then((x) => x.items)
            .catch(() => null),
          analyticsOutcomesApi
            .getCourseXFeature({ version: 'v1', from: fromOutcomesMonth, to: toOutcomesMonth, limit: 20000 })
            .then((x) => x.items)
            .catch(() => null),
        ]);    

        if (!mounted) return;

        setLogs(outcomeData);
        setWeeklyNotifSummary(weeklySummary);
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
      } catch (e: any) {
        if (!mounted) return;
        setError(e?.message ?? 'failed to load outcomes');
      } finally {
        if (!mounted) return;
        setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfWeek = new Date(startOfToday);
  startOfWeek.setDate(startOfWeek.getDate() - 6); // 過去7日
  const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
  const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0);

  const parseDeadline = (x: OutcomeLog) => new Date(x.deadline);

  const inRange = (d: Date, from: Date, to: Date) =>
    d.getTime() >= from.getTime() && d.getTime() <= to.getTime();

  const weeklyLogs = useMemo(
    () => logs.filter((x) => inRange(parseDeadline(x), startOfWeek, startOfToday)),
    [logs, startOfWeek, startOfToday]
  );

  const monthlyLogs = useMemo(
    () => logs.filter((x) => inRange(parseDeadline(x), startOfMonth, endOfMonth)),
    [logs, startOfMonth, endOfMonth]
  );

  const calcRate = (subset: OutcomeLog[]) => {
    const total = subset.length;
    if (total === 0) return { total: 0, done: 0, rate: 0 };
    const done = subset.filter((x) => x.outcome === 'done').length;
    return { total, done, rate: Math.round((done / total) * 100) };
  };

  const weekly = useMemo(() => calcRate(weeklyLogs), [weeklyLogs]);
  const monthly = useMemo(() => calcRate(monthlyLogs), [monthlyLogs]);

  // ✅ Priority 3-A: 表示対象（週 / 月）
  const chosenSummary = bucket === 'week' ? summaryWeek : summaryMonth;
  const chosenByCourse = bucket === 'week' ? byCourseWeek : byCourseMonth;
  const chosenByFeature = bucket === 'week' ? byFeatureWeek : byFeatureMonth;
  const chosenCourseX = bucket === 'week' ? courseXWeek : courseXMonth;

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

  // ✅ 表示用にソート（missed_rate desc）
  const sortedByFeature = useMemo(() => {
    if (!chosenByFeature) return null;
    return [...chosenByFeature].sort((a, b) => toPercent(b.missed_rate) - toPercent(a.missed_rate));
  }, [chosenByFeature]);

  const worstFeature = sortedByFeature?.[0] ?? null;

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

  const labelFeatureValue = (v: OutcomesByFeatureRow['feature_value'], key?: string) => {
    if (v == null) return '—';

    if (key === 'deadline_dow_jst') {
      const n = Number(v);
      const days = ['月', '火', '水', '木', '金', '土', '日'];
      return Number.isFinite(n) && n >= 0 && n <= 6 ? days[n] : String(v);
    }

    if (key === 'deadline_hour_jst') {
      const h = Number(v);
      if (!Number.isFinite(h)) return String(v);
      if (h <= 5) return `深夜（${h}時）`;
      if (h <= 10) return `朝（${h}時）`;
      if (h <= 16) return `昼（${h}時）`;
      if (h <= 21) return `夜（${h}時）`;
      return `深夜（${h}時）`;
    }

    if (typeof v === 'boolean') return v ? 'Yes' : 'No';
    return String(v);
  };

  const toPercent = (v: number | null | undefined) => {
    if (v == null) return 0;
    const n = Number(v);
    if (!Number.isFinite(n)) return 0;
    return n <= 1 ? Math.round(n * 100) : Math.round(n);
  };

  const courseKeyOf = (r: OutcomesByCourseRow) =>
    r.course_name || r.course_key || r.course_hash || 'unknown';

  const labelCourse = (raw: string) => {
    if (!raw) return 'unknown';
    // hash っぽい値でも見やすく短縮（表示だけ。仕様変更ではない）
    return raw.length > 16 ? `${raw.slice(0, 8)}…${raw.slice(-4)}` : raw;
  };

  const summaryRate = chosenSummary ? toPercent(chosenSummary.done_rate) : null;

  // ✅ 週次通知反応（summary API 1発）
  const weeklySummaryLoaded = weeklyNotifSummary !== null;
  const weeklyCreated = weeklyNotifSummary?.total ?? 0;
  const weeklyDismissed = weeklyNotifSummary?.dismissed ?? 0;
  const weeklyDismissRate = weeklyNotifSummary?.dismiss_rate ?? 0;

  const weeklyEvents = weeklyNotifSummary?.webpush_events;
  const weeklySentEvents = weeklyEvents?.sent ?? 0;

  // NotifStatsCard は props 形を変えない（最小diff）
  const weeklySent = weeklyEvents?.sent ?? 0;
  const weeklyFailed = weeklyEvents?.failed ?? 0;
  const weeklyDeactivated = weeklyEvents?.deactivated ?? 0;

  const summaryInappTotal = latestRunSummary?.inapp?.total ?? 0;
  const summaryDismissed = latestRunSummary?.inapp?.dismissed_count ?? 0;
  const summaryDismissRate = latestRunSummary?.inapp?.dismiss_rate ?? 0;

  // ✅ 表示用にソート（backendの並びに依存しない）
  const sortedByCourse = useMemo(() => {
    if (!chosenByCourse) return null;
    return [...chosenByCourse].sort((a, b) => toPercent(b.missed_rate) - toPercent(a.missed_rate));
  }, [chosenByCourse]);

  const worstCourse = sortedByCourse?.[0] ?? null;

  if (loading) {
    return <div style={{ color: 'rgba(255,255,255,.7)' }}>Loading…</div>;
  }
  if (error) {
    return <div style={{ color: '#fca5a5' }}>Failed: {error}</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
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

      <StatsCard
        title={`達成率（${bucket === 'week' ? '週' : '月'}）`}
        subtitle={chosenSummary ? 'analytics/outcomes/summary（read-only SSOT）' : '（集計がまだありません）'}
        rate={summaryRate ?? 0}
        total={chosenSummary?.total ?? 0}
        done={chosenSummary?.done ?? 0}
      />

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
          落ちやすい授業（missed率ランキング）
        </div>
        <div
          style={{
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
            落ちやすい特徴（feature別 missed率）
          </div>
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
              授業ごとの「落ちやすい理由」（course × feature）
            </div>

            <div style={{ marginBottom: '0.75rem', fontSize: '0.8rem', color: 'rgba(255,255,255,.62)' }}>
              analytics/outcomes/course-x-feature（read-only SSOT）
            </div>

            {courseHashList.length === 0 ? (
              <div style={{ opacity: 0.7 }}>（まだ集計対象がありません）</div>
            ) : (
              <>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.65rem' }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 800, opacity: 0.9 }}>対象授業:</div>
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
                            #{idx + 1} {labelFeatureKey(r.feature_key)} = {labelFeatureValue(r.feature_value, r.feature_key)}
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
              </>
            )}
          </div>

          {worstFeature && (
            <div style={{ marginBottom: '0.6rem', fontSize: '0.9rem', fontWeight: 800 }}>
              いちばん要注意：
              {labelFeatureKey(worstFeature.feature_key)} = {labelFeatureValue(worstFeature.feature_value, worstFeature.feature_key)}（
              {toPercent(worstFeature.missed_rate)}% / missed {worstFeature.missed}/{worstFeature.total}
              ）
            </div>
          )}

          <div style={{ marginBottom: '0.75rem', fontSize: '0.8rem', color: 'rgba(255,255,255,.62)' }}>
            analytics/outcomes/missed-by-feature（read-only SSOT）
          </div>

          {!sortedByFeature || sortedByFeature.length === 0 ? (
            <div style={{ opacity: 0.7 }}>（まだ集計対象がありません）</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
              {sortedByFeature.slice(0, 8).map((r, idx) => (
                <div
                  key={`${r.feature_key}-${String(r.feature_value)}-${idx}`}
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
                      #{idx + 1} {labelFeatureKey(r.feature_key)} = {labelFeatureValue(r.feature_value, r.feature_key)}
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
        </div>
        {worstCourse && (
          <div style={{ marginBottom: '0.6rem', fontSize: '0.9rem', fontWeight: 800 }}>
            いちばん要注意：
            {labelCourse(courseKeyOf(worstCourse))}（
            {toPercent(worstCourse.missed_rate)}% / missed {worstCourse.missed}/{worstCourse.total}
            ）
          </div>
        )}
        <div style={{ marginBottom: '0.75rem', fontSize: '0.8rem', color: 'rgba(255,255,255,.62)' }}>
          {chosenByCourse ? 'analytics/outcomes/by-course（read-only SSOT）' : '（集計がまだありません）'}
        </div>

        {!sortedByCourse || sortedByCourse.length === 0 ? (
          <div style={{ opacity: 0.7 }}>（まだ集計対象がありません）</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
            {sortedByCourse.slice(0, 8).map((r, idx) => (
              <div
                key={`${courseKeyOf(r)}-${idx}`}
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
                    #{idx + 1} {labelCourse(courseKeyOf(r))}
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
      </div>
      <StatsCard
        title="今週（直近7日）の達成率"
        subtitle={
          weeklySummaryLoaded
            ? "InAppNotification（資産）+ extra.webpush（観測）ベース"
            : "通知サマリ取得失敗（暫定値）"
        }
        rate={weekly.rate}
        total={weekly.total}
        done={weekly.done}
      />

      <NotifStatsCard
        title="今週の通知反応"
        subtitle="InAppNotification（資産）+ extra.webpush（観測）ベース"
        created={weeklyCreated}
        dismissed={weeklyDismissed}
        dismissRate={weeklyDismissRate}
        sent={weeklySent}
        failed={weeklyFailed}
        deactivated={weeklyDeactivated}
        sentEvents={weeklySentEvents}
      />

      <StatsCard
        title="今月の達成率"
        subtitle="OutcomeLog（締切到達時点の結果）ベース"
        rate={monthly.rate}
        total={monthly.total}
        done={monthly.done}
      />

      <RunStatsCard
        title="最新Runの観測"
        subtitle="NotificationRun（cron集計）× InAppNotification（資産）で突合"
        run={latestRun}
        summary={latestRunSummary}
        inappTotal={summaryInappTotal}
        dismissed={summaryDismissed}
        dismissRate={summaryDismissRate}
      />
    </div>
  );
};

interface StatsCardProps {
  title: string;
  subtitle: string;
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
      <div style={{ marginBottom: '0.75rem', fontSize: '0.8rem', color: 'rgba(255,255,255,.62)' }}>
        {subtitle}
      </div>

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

interface RunStatsCardProps {
  title: string;
  subtitle: string;
  run: NotificationRun | null;
  summary: RunSummary | null;
  inappTotal: number;
  dismissed: number;
  dismissRate: number;
}

const RunStatsCard: React.FC<RunStatsCardProps> = ({
  title,
  subtitle,
  run,
  summary,
  inappTotal,
  dismissed,
  dismissRate,
}) => {
  const clampedRate = Math.max(0, Math.min(100, dismissRate));

  const runId = run?.id ?? null;
  const runStatus = run?.status ?? 'unknown';

  const runCounters = run
    ? {
        inapp_created: Number(run.inapp_created ?? 0),
        webpush_sent: Number(run.webpush_sent ?? 0),
        webpush_failed: Number(run.webpush_failed ?? 0),
        webpush_deactivated: Number(run.webpush_deactivated ?? 0),
      }
    : null;

  const summaryCounters = summary
    ? {
        inapp_total: Number(summary.inapp.total ?? 0),
        delivered: Number(summary.inapp.webpush.delivered ?? 0),
        failed: Number(summary.inapp.webpush.failed ?? 0),
        deactivated: Number(summary.inapp.webpush.deactivated ?? 0),
        unknown: Number(summary.inapp.webpush.unknown ?? 0),
        events: {
          sent: Number(summary.inapp.webpush.events?.sent ?? 0),
          failed: Number(summary.inapp.webpush.events?.failed ?? 0),
          deactivated: Number(summary.inapp.webpush.events?.deactivated ?? 0),
          skipped: Number(summary.inapp.webpush.events?.skipped ?? 0),
          unknown: Number(summary.inapp.webpush.events?.unknown ?? 0),
        },
      }
    : null;

  return (
    <div
      style={{
        padding: '1rem 1.1rem',
        borderRadius: 18,
        border: '1px solid rgba(255,255,255,.12)',
        background:
          'radial-gradient(circle at 20% 0%, rgba(251,146,60,.16), rgba(255,255,255,.06) 45%, rgba(255,255,255,.04))',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        boxShadow: '0 14px 40px rgba(0,0,0,.38)',
        color: 'rgba(255,255,255,.92)',
      }}
    >
      <div style={{ marginBottom: '0.25rem', fontWeight: 800, letterSpacing: '0.02em' }}>
        {title}
      </div>
      <div style={{ marginBottom: '0.75rem', fontSize: '0.8rem', color: 'rgba(255,255,255,.62)' }}>
        {subtitle}
      </div>

      <div style={{ fontSize: '0.9rem', color: 'rgba(255,255,255,.82)', marginBottom: '0.7rem' }}>
        <div>run_id: {runId ?? '—'} / status: {runStatus}</div>
        {run?.error_summary ? <div style={{ color: 'rgba(252,165,165,.9)' }}>error: {run.error_summary}</div> : null}
      </div>

      {/* dismiss rate */}
      <div
        style={{
          position: 'relative',
          height: 14,
          borderRadius: 9999,
          backgroundColor: 'rgba(255,255,255,.10)',
          overflow: 'hidden',
          marginBottom: '0.5rem',
        }}
      >
        <div
          style={{
            width: `${clampedRate}%`,
            height: '100%',
            borderRadius: 9999,
            background: 'linear-gradient(90deg, rgba(251,146,60,.95), rgba(14,165,233,.95))',
            transition: 'width 0.25s ease-out',
          }}
        />
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: 'rgba(255,255,255,.78)' }}>
        <span>dismiss率: {clampedRate}%</span>
        <span>{dismissed} / {inappTotal} 件（summary）</span>
      </div>

      <div style={{ marginTop: '0.7rem', fontSize: '0.82rem', color: 'rgba(255,255,255,.72)' }}>
        <div style={{ marginBottom: '0.35rem', fontWeight: 700, color: 'rgba(255,255,255,.8)' }}>Run集計（cron側）</div>
        <div>
          inapp_created={runCounters?.inapp_created ?? '—'} / webpush sent={runCounters?.webpush_sent ?? '—'} failed={runCounters?.webpush_failed ?? '—'} deact={runCounters?.webpush_deactivated ?? '—'}
        </div>

        <div style={{ marginTop: '0.6rem', marginBottom: '0.35rem', fontWeight: 700, color: 'rgba(255,255,255,.8)' }}>資産集計（InAppNotification側）</div>
        <div>
          inapp_total={summaryCounters?.inapp_total ?? '—'} / delivered={summaryCounters?.delivered ?? '—'} failed={summaryCounters?.failed ?? '—'} deact={summaryCounters?.deactivated ?? '—'} unknown={summaryCounters?.unknown ?? '—'}
        </div>

        <div style={{ marginTop: '0.25rem' }}>
          events: sent={summaryCounters?.events.sent ?? '—'} failed={summaryCounters?.events.failed ?? '—'} deact={summaryCounters?.events.deactivated ?? '—'} skipped={summaryCounters?.events.skipped ?? '—'} unknown={summaryCounters?.events.unknown ?? '—'}
        </div>

        <div style={{ marginTop: '0.5rem', color: 'rgba(255,255,255,.6)' }}>
          ※ 「Run集計」と「資産集計」がズレたら、観測/監査の入口になる（M&A説明しやすい）
        </div>
      </div>
    </div>
  );
};


interface NotifStatsCardProps {
  title: string;
  subtitle: string;
  created: number;
  dismissed: number;
  dismissRate: number;
  sent: number;
  failed: number;
  deactivated: number;
  sentEvents: number;
}

const NotifStatsCard: React.FC<NotifStatsCardProps> = ({
  title,
  subtitle,
  created,
  dismissed,
  dismissRate,
  sent,
  failed,
  deactivated,
  sentEvents,
}) => {
  const clampedRate = Math.max(0, Math.min(100, dismissRate));

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
      <div style={{ marginBottom: '0.25rem', fontWeight: 800, letterSpacing: '0.02em' }}>
        {title}
      </div>
      <div style={{ marginBottom: '0.75rem', fontSize: '0.8rem', color: 'rgba(255,255,255,.62)' }}>
        {subtitle}
      </div>

      <div style={{ fontSize: '0.9rem', color: 'rgba(255,255,255,.82)', marginBottom: '0.6rem' }}>
        <div>作成: {created} 件</div>
        <div>dismiss: {dismissed} 件</div>
        <div>反応率(dismiss): {clampedRate}%</div>
      </div>

      <div
        style={{
          position: 'relative',
          height: 14,
          borderRadius: 9999,
          backgroundColor: 'rgba(255,255,255,.10)',
          overflow: 'hidden',
          marginBottom: '0.6rem',
        }}
      >
        <div
          style={{
            width: `${clampedRate}%`,
            height: '100%',
            borderRadius: 9999,
            background: 'linear-gradient(90deg, rgba(168,85,247,.95), rgba(14,165,233,.95))',
            transition: 'width 0.25s ease-out',
          }}
        />
      </div>

      <div style={{ fontSize: '0.82rem', color: 'rgba(255,255,255,.72)' }}>
        <div>WebPush: sent={sent} failed={failed} deactivated={deactivated}</div>
        <div>sentイベント数: {sentEvents}（通知レコード単位）</div>
      </div>
    </div>
  );
};
