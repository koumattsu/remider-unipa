// frontend/src/components/StatsView.tsx

import { useEffect, useMemo, useState } from 'react';
import { outcomesApi, OutcomeLog } from '../api/outcomes';
import { fetchInAppNotifications, InAppNotification } from '../api/notifications';
import { fetchLatestNotificationRun, fetchRunSummary, NotificationRun, RunSummary } from '../api/notificationRuns';
import { Task } from '../types';


interface StatsViewProps {
  tasks: Task[]; // 互換のため残す（今後 outcomes だけにするなら削除OK）
}

export const StatsView: React.FC<StatsViewProps> = ({ tasks: _tasks }) => {
  const [logs, setLogs] = useState<OutcomeLog[]>([]);
  const [notifs, setNotifs] = useState<InAppNotification[]>([]);
  const [latestRun, setLatestRun] = useState<NotificationRun | null>(null);
  const [latestRunSummary, setLatestRunSummary] = useState<RunSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        setLoading(true);
        setError(null);
        // まずは全件取得（重くなったら from/to で絞る）
        const run = await fetchLatestNotificationRun().catch(() => null);
        const [outcomeData, notifData, summary] = await Promise.all([
          outcomesApi.list(),
          fetchInAppNotifications(200, { includeDismissed: true }),
          run?.id ? fetchRunSummary(run.id).catch(() => null) : Promise.resolve(null),
        ]);

        if (!mounted) return;

        setLogs(outcomeData);
        setNotifs(notifData);
        setLatestRun(run);
        setLatestRunSummary(summary);

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

  const parseNotifCreatedAt = (n: InAppNotification) => new Date(n.created_at);

  const weeklyNotifs = useMemo(
    () => notifs.filter((n) => inRange(parseNotifCreatedAt(n), startOfWeek, startOfToday)),
    [notifs, startOfWeek, startOfToday]
  );

  const runNotifs = useMemo(() => {
    if (!latestRun?.id) return [];
    return notifs.filter((n) => n.run_id === latestRun.id);
  }, [notifs, latestRun]);

  const runDismissed = useMemo(() => runNotifs.filter((n) => !!n.dismissed_at).length, [runNotifs]);

  const runDismissRate = useMemo(() => {
    const total = runNotifs.length;
    if (total === 0) return 0;
    return Math.round((runDismissed / total) * 100);
  }, [runNotifs, runDismissed]);


  const notifWeeklyStats = useMemo(() => {
    const created = weeklyNotifs.length;
    const dismissed = weeklyNotifs.filter((n) => !!n.dismissed_at).length;
    const dismissRate = created === 0 ? 0 : Math.round((dismissed / created) * 100);

    let sent = 0;
    let failed = 0;
    let deactivated = 0;
    let sentEvents = 0;

    for (const n of weeklyNotifs) {
      const wp = (n.extra as any)?.webpush;
      if (!wp) continue;

      sent += Number(wp.sent ?? 0);
      failed += Number(wp.failed ?? 0);
      deactivated += Number(wp.deactivated ?? 0);

      if (wp.status === 'sent') sentEvents += 1;
    }

    return { created, dismissed, dismissRate, sent, failed, deactivated, sentEvents };
  }, [weeklyNotifs]);


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

  if (loading) {
    return <div style={{ color: 'rgba(255,255,255,.7)' }}>Loading…</div>;
  }
  if (error) {
    return <div style={{ color: '#fca5a5' }}>Failed: {error}</div>;
  }

    return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <StatsCard
        title="今週（直近7日）の達成率"
        subtitle="OutcomeLog（締切到達時点の結果）ベース"
        rate={weekly.rate}
        total={weekly.total}
        done={weekly.done}
      />

      <NotifStatsCard
        title="今週の通知反応"
        subtitle="InAppNotification（資産）+ extra.webpush（観測）ベース"
        created={notifWeeklyStats.created}
        dismissed={notifWeeklyStats.dismissed}
        dismissRate={notifWeeklyStats.dismissRate}
        sent={notifWeeklyStats.sent}
        failed={notifWeeklyStats.failed}
        deactivated={notifWeeklyStats.deactivated}
        sentEvents={notifWeeklyStats.sentEvents}
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
        inappTotal={runNotifs.length}
        dismissed={runDismissed}
        dismissRate={runDismissRate}
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
        <span>{dismissed} / {inappTotal} 件（run_id一致）</span>
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
