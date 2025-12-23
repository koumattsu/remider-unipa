// frontend/src/utils/taskTime.ts
import type { Task } from '../types';

const JST_OFFSET_MS = 9 * 60 * 60 * 1000;
const HOUR_MS = 60 * 60 * 1000;

const toJst = (d: Date) => new Date(d.getTime() + JST_OFFSET_MS);

/**
 * ✅ 「今日」= JSTで 1:00〜24:30 の感覚
 * - 0:00〜0:59は前日扱い
 */
export const isTodayTaskJst = (deadlineIso: string, now = new Date()) => {
  const d = toJst(new Date(deadlineIso));
  const n = toJst(now);

  if (d.getHours() < 1) d.setDate(d.getDate() - 1);

  return (
    d.getFullYear() === n.getFullYear() &&
    d.getMonth() === n.getMonth() &&
    d.getDate() === n.getDate()
  );
};

/**
 * ✅ 「管理中」(Allタブ default)
 * - deadline >= now: 全表示（完了/未完）
 * - now-24h <= deadline < now:
 *    - 未完は表示
 *    - 完了は「締切後に完了」(completed_at > deadline) のみ表示
 */
const isActiveManaged = (t: Task, now = new Date()) => {
  const deadline = new Date(t.deadline);
  if (deadline >= now) return true;

  const dayAgo = new Date(now.getTime() - 24 * HOUR_MS);
  if (!(deadline >= dayAgo && deadline < now)) return false;

  if (!t.is_done) return true;

  const completedAt = t.completed_at ? new Date(t.completed_at) : null;
  return !!(completedAt && completedAt > deadline);
};

export const isOverdueIncomplete = (t: Task, now = new Date()) =>
  new Date(t.deadline) < now && t.is_done === false;

const isInDeadlineIncomplete = (t: Task, now = new Date()) =>
  new Date(t.deadline) >= now && t.is_done === false;

export type AllViewMode = 'active' | 'overdue' | 'incomplete';

export const getAllTasksByViewMode = (
  tasks: Task[],
  viewMode: AllViewMode,
  now = new Date()
) => {
  if (viewMode === 'overdue') {
    return tasks.filter((t) => isOverdueIncomplete(t, now));
  }
  if (viewMode === 'incomplete') {
    return tasks.filter((t) => isInDeadlineIncomplete(t, now));
  }
  // default = active（管理中）
  return tasks.filter((t) => isActiveManaged(t, now));
};
