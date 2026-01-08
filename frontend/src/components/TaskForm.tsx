// frontend/src/components/TaskForm.tsx

import { useState, useEffect } from 'react';
import { Task } from '../types';
import { tasksApi } from '../api/tasks';

type TaskFormData = {
  title: string;
  memo: string;
};

interface TaskFormProps {
  onTaskCreated: () => void;
  defaultDeadlineDate?: string;
  onTaskAddedLocal?: (task: Task) => void;
  onTaskReplacedLocal?: (tempId: number, realTask: Task) => void;
  onTaskCreateFailedLocal?: (tempId: number) => void;
}

export const TaskForm: React.FC<TaskFormProps> = ({
  onTaskCreated,
  defaultDeadlineDate,
  onTaskAddedLocal,
  onTaskReplacedLocal,
  onTaskCreateFailedLocal,
}) => {
  const [formData, setFormData] = useState<TaskFormData>({ title: '', memo: '' });
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [deadlineDate, setDeadlineDate] = useState(defaultDeadlineDate ?? ''); 
  const [deadlineHour, setDeadlineHour] = useState('24'); // "1"〜"24"、デフォルト24時
  const [deadlineMinute, setDeadlineMinute] = useState('00'); // "00" or "30"

  // defaultDeadlineDate が変わったら deadlineDate に反映
  useEffect(() => {
    setDeadlineDate(defaultDeadlineDate ?? '');
  }, [defaultDeadlineDate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    let tempId: number | null = null;

    try {
      if (!formData.title.trim()) {
        alert('タイトルを入力してください');
        return;
      }
      if (!deadlineDate) {
        alert('締切日を選択してください');
        return;
      }

      const hourNum = Number(deadlineHour);
      const minuteNum = Number(deadlineMinute);

      // "YYYY-MM-DD" を分解（new Date('YYYY-MM-DD') のUTC罠を避ける）
      const [y, m, d] = deadlineDate.split('-').map(Number);

      // ローカル(JST)として Date を作る
      const dateObj =
        hourNum === 24
          ? new Date(y, m - 1, d + 1, 0, minuteNum, 0, 0) // 24:xx → 翌日0:xx
          : new Date(y, m - 1, d, hourNum, minuteNum, 0, 0);

      // サーバーにはUTCで送る（例: 2025-12-14T14:00:00.000Z）
      const deadlineStr = dateObj.toISOString();
      tempId = -Date.now();
      const tempTask: Task = {
        id: tempId,
        title: formData.title.trim(),
        course_name: '__manual__',
        memo: formData.memo.trim(),
        deadline: deadlineStr,
        is_done: false,
        should_notify: true,
        auto_notify_disabled_by_done: false,
        weekly_task_id: null,
      };
      onTaskAddedLocal?.(tempTask);

      // ✅ ② API成功で仮→実に置換
      const real = await tasksApi.create({
        title: tempTask.title,
        course_name: tempTask.course_name,
        memo: tempTask.memo,
        deadline: tempTask.deadline,
        should_notify: true,
      });
      onTaskReplacedLocal?.(tempId, real);

      // reset
      setFormData({ title: '', memo: '' });
      setDeadlineDate('');
      setDeadlineHour('24');
      setDeadlineMinute('00');
      onTaskCreated();
    } catch (error) {
      console.error('課題の作成に失敗しました:', error);
      if (tempId !== null) onTaskCreateFailedLocal?.(tempId);
      // ✅ ③ rollback（仮タスク削除）
      // tempId がスコープに必要なので、上の tempId/tempTask を try の外に出してもOK
      // ここでは「tempIdが存在する場合だけ」削除できるようにする
      // -> 下の “小さい仕上げ” を見て
      alert('課題の作成に失敗しました');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="glass-strong glass-card" style={{ marginBottom: '2rem' }}>
      <h2 className="glass-title">課題を追加</h2>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '1rem' }}>
          <label className="glass-label">タイトル *</label>
          <input
            type="text"
            value={formData.title}
            onChange={(e) => setFormData({ ...formData, title: e.target.value })}
            className="glass-field"
            placeholder="例：〇〇授業"
          />
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label className="glass-label">メモ</label>
          <textarea
            value={formData.memo ?? ''}
            onChange={(e) => setFormData({ ...formData, memo: e.target.value })}
            className="glass-field"
            placeholder="補足があれば"
            rows={3}
            style={{ resize: 'vertical' }}
          />
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label className="glass-label">締切日時 *</label>

          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            {/* 日付 */}
            <div style={{ position: 'relative', flex: 1 }}>
              <input
                type="date"
                value={deadlineDate}
                onChange={(e) => setDeadlineDate(e.target.value)}
                required
                className={`glass-field ${defaultDeadlineDate ? 'date-right' : ''}`}
              />
            </div>
            {/* 時 */}
            <select
              value={deadlineHour}
              onChange={(e) => setDeadlineHour(e.target.value)}
              className="glass-field"
              style={{ width: 130 }}
            >
              {Array.from({ length: 24 }, (_, i) => {
                const h = i + 1;
                const label = `${String(h).padStart(2, '0')}:00`;
                return (
                  <option key={h} value={h.toString()}>
                    {label}
                  </option>
                );
              })}
            </select>

            {/* 分 */}
            <select
              value={deadlineMinute}
              onChange={(e) => setDeadlineMinute(e.target.value)}
              className="glass-field"
              style={{ width: 90 }}
            >
              <option value="00">00</option>
              <option value="30">30</option>
            </select>
          </div>

          <p className="glass-help">
            ※0時締切の課題は、日付を1日前にして「24:00」で登録してください。
            （例：12/1 の 0:00 締切 → 11/30 の 24:00）
          </p>
        </div>

        <button type="submit" disabled={isSubmitting} className="btn-primary">
          {isSubmitting ? '作成中...' : '課題を追加'}
        </button>
      </form>
    </div>
  );
};