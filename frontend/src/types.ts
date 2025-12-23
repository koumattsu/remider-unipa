// frontend/src/types.ts

export interface Task {
  id: number;
  title: string;
  course_name: string;
  deadline: string;
  memo?: string | null;
  is_done: boolean;
  completed_at?: string | null; // ✅ 締切前完了/締切後完了の判定用
  should_notify: boolean | null;
  auto_notify_disabled_by_done: boolean; // ← 追加（バックエンドTaskResponseに合わせる）
  weekly_task_id?: number | null;
}

// 課題作成用
export interface TaskCreate {
  title: string;
  course_name: string;
  deadline: string;
  memo?: string | null;
  should_notify: boolean;
  weekly_task_id?: number | null;
}

export interface TaskUpdate {
  title?: string;
  course_name?: string;
  deadline?: string;
  memo?: string | null;
  is_done?: boolean;
  should_notify?: boolean;
  weekly_task_id?: number | null;
}

/* 👇 ここから毎週タスク関連 */

// 毎週タスクのテンプレ用
export interface WeeklyTask {
  id: number;
  title: string;
  course_name?: string | null;
  memo?: string | null;
  // 0 = 月曜, 1 = 火曜, ... 6 = 日曜
  weekday: number;
  time_hour: number;
  time_minute: number;
  is_active: boolean;
}

// 作成用
export interface WeeklyTaskCreate {
  title: string;
  course_name?: string | null;
  memo?: string | null;
  weekday: number;
  time_hour: number;
  time_minute: number;
  is_active: boolean;
}

// 更新用（全部オプショナル）
export interface WeeklyTaskUpdate {
  title?: string;
  course_name?: string | null;
  memo?: string | null;
  weekday?: number;
  time_hour?: number;
  time_minute?: number;
  is_active?: boolean;
}

export interface NotificationSetting {
  id: number;
  user_id: number;
  reminder_offsets_hours: number[];      // 例: [3, 24]
  daily_digest_time: string;            // "08:00" など
  enable_morning_notification: boolean; // 朝通知 ON/OFF
}

// update 用（NotificationSettings.tsx の import 用）
export interface NotificationSettingUpdate {
  reminder_offsets_hours: number[];
  daily_digest_time: string;
  enable_morning_notification: boolean;
}
