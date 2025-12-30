// frontend/src/types/index.ts

export interface User {
  id: number;
  line_user_id: string;
  display_name: string;
  university: string | null;
  plan: string;
}

export interface Task {
  id: number;
  user_id: number;
  title: string;
  course_name: string;
  deadline: string; // ISO 8601形式
  memo: string | null;
  is_done: boolean;
  created_at: string;
  updated_at: string;
}

export interface TaskCreate {
  title: string;
  course_name: string;
  deadline: string; // ISO 8601形式
  memo?: string | null;
}

export interface TaskUpdate {
  title?: string;
  course_name?: string;
  deadline?: string;
  memo?: string | null;
  is_done?: boolean;
}

export interface NotificationSetting {
  id: number;
  user_id: number;
  reminder_offsets_hours: number[];
  daily_digest_time: string;
  enable_morning_notification: boolean;
  enable_webpush: boolean;
}

export interface NotificationSettingUpdate {
  reminder_offsets_hours: number[];
  daily_digest_time: string;
  enable_morning_notification: boolean;
  enable_webpush: boolean;
}
