// frontend/src/components/TaskForm.tsx

import { useState, useEffect} from 'react';
import { TaskCreate } from '../types';
import { tasksApi } from '../api/tasks';

interface TaskFormProps {
  onTaskCreated: () => void;
  defaultDeadlineDate?: string; 
}

export const TaskForm: React.FC<TaskFormProps> = ({ onTaskCreated, defaultDeadlineDate}) => {
  const [formData, setFormData] = useState<
    Omit<TaskCreate, 'deadline' | 'should_notify'>
  >({
    title: '',
    course_name: '',
    memo: '',
  });
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

    try {
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

      await tasksApi.create({
        ...formData,
        title: formData.title.trim(),
        course_name: formData.course_name?.trim() || '',
        memo: formData.memo?.trim() || '',
        deadline: deadlineStr,
        should_notify: true,
      });

      // reset
      setFormData({ title: '', course_name: '', memo: '' });
      setDeadlineDate('');
      setDeadlineHour('24');
      setDeadlineMinute('00');
      onTaskCreated();
    } catch (error) {
      console.error('課題の作成に失敗しました:', error);
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
            required
            className="glass-field"
            placeholder="例：レポート提出"
          />
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label className="glass-label">内容</label>
          <input
            type="text"
            value={formData.course_name}
            onChange={(e) =>
              setFormData({ ...formData, course_name: e.target.value })
            }
            className="glass-field"
            placeholder="例：〇〇講義 / 第3回"
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
                className="glass-field"
              />

              {/* 未選択時だけ中央にアイコン（文字はCSSで透明化済み） */}
              {!deadlineDate && (
                <div
                  style={{
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    pointerEvents: 'none',
                    fontSize: '1.15rem',
                    color: 'rgba(255,255,255,.55)',
                  }}
                >
                  📅
                </div>
              )}
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