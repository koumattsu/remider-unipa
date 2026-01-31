// frontend/src/analytics/suggestedActions.ts
import type { NotificationSetting, NotificationSettingUpdate } from '../types';
import type { OutcomesCourseXFeatureRow } from '../api/analyticsOutcomes';

export type SuggestedAction = {
  id: string;
  title: string;
  description: string;
  // null の場合は「手動アクション」（ボタン非表示）
  patch: NotificationSettingUpdate | null;
  reason_keys?: string[];
};

const asBool = (v: any): boolean | null => {
  if (typeof v === 'boolean') return v;
  if (typeof v === 'string') {
    const s = v.trim().toLowerCase();
    if (s === 'true') return true;
    if (s === 'false') return false;
  }
  return null;
};

const asNumber = (v: any): number | null => {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

export function buildSuggestedActions(
  rows: OutcomesCourseXFeatureRow[],
  currentNotifSetting: NotificationSetting | null
): SuggestedAction[] {
  const actions: SuggestedAction[] = [];

  // 現在値（無ければ安全デフォルト）
  const base: NotificationSettingUpdate = {
    reminder_offsets_hours: currentNotifSetting?.reminder_offsets_hours ?? [],
    daily_digest_time: currentNotifSetting?.daily_digest_time ?? '08:00',
    enable_morning_notification:
      currentNotifSetting?.enable_morning_notification !== undefined
        ? currentNotifSetting.enable_morning_notification
        : true,
    enable_webpush: currentNotifSetting?.enable_webpush ?? false,
  };

  const hasWeekend = rows.some(
    (r) => r.feature_key === 'deadline_is_weekend' && asBool(r.feature_value) === true
  );

  const hasLateNight = rows.some((r) => {
    if (r.feature_key !== 'deadline_hour_jst') return false;
    const h = asNumber(r.feature_value);
    return h !== null && h >= 0 && h <= 5;
  });

  const hasNoMemo = rows.some(
    (r) => r.feature_key === 'has_memo' && asBool(r.feature_value) === false
  );

  if (hasWeekend) {
    actions.push({
      id: 'weekend_enable_morning',
      title: '週末締切が多い → 朝通知をON（継続チェックの起点を作る）',
      description: '週末締切が原因で missed が多いため、朝通知をONにして着手トリガーを作ります。',
      reason_keys: ['deadline_is_weekend', 'deadline_dow_jst'],
      patch: {
        ...base,
        enable_morning_notification: true,
      },
    });
  }

  if (hasLateNight) {
    actions.push({
      id: 'latenight_enable_webpush_and_1h',
      title: '深夜締切が多い → Web Push と 1時間前通知をON',
      description: '深夜締切は見落としやすいので、アプリ通知（Web Push）と1時間前通知で拾います。',
      reason_keys: ['deadline_hour_jst'],
      patch: {
        ...base,
        enable_webpush: true,
        reminder_offsets_hours: [1],
      },
    });
  }

  if (hasNoMemo) {
    actions.push({
      id: 'add_memo',
      title: 'メモ無しが多い → タスクに1行メモを追加',
      description: '「何をやるか」を1行で書くと、完了率が上がりやすいです（これは手動アクション）。',
      reason_keys: ['has_memo'],
      patch: null,
    });
  }

  // 空UI回避（最低1個）
  if (actions.length === 0) {
    actions.push({
      id: 'generic',
      title: 'まずは 1時間前通知（無料の基本）をONにする',
      description: '最小の介入で取りこぼしを減らします。',
      patch: {
        ...base,
        reminder_offsets_hours: [1],
      },
    });
  }

  return actions;
}
