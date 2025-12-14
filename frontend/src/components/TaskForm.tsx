// frontend/src/components/TaskForm.tsx

import { useState } from 'react';
import { TaskCreate } from '../types';
import { tasksApi } from '../api/tasks';

interface TaskFormProps {
  onTaskCreated: () => void;
}

export const TaskForm: React.FC<TaskFormProps> = ({ onTaskCreated }) => {
  const [formData, setFormData] = useState<
    Omit<TaskCreate, 'deadline' | 'should_notify'>
  >({
    title: '',
    course_name: '',
    memo: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [deadlineDate, setDeadlineDate] = useState('');   // 例: "2025-11-30"
  const [deadlineHour, setDeadlineHour] = useState('24'); // "1"〜"24"、デフォルト24時
  const [deadlineMinute, setDeadlineMinute] = useState('00'); // "00" or "30"

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
    <div style={{ marginBottom: '2rem', padding: '1.5rem', border: '1px solid #ddd', borderRadius: '8px' }}>
      <h2 style={{ marginTop: 0 }}>課題を追加</h2>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
            タイトル *
          </label>
          <input
            type="text"
            value={formData.title}
            onChange={(e) => setFormData({ ...formData, title: e.target.value })}
            required
            style={{ width: '100%', padding: '0.5rem', fontSize: '1rem' }}
          />
        </div>
        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
            内容
          </label>
          <input
            type="text"
            value={formData.course_name}
            onChange={(e) => setFormData({ ...formData, course_name: e.target.value })}
            // 必須ではないので required は付けない
            style={{ width: '100%', padding: '0.5rem', fontSize: '1rem' }}
          />
        </div>

        
        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
            締切日時 *
          </label>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
            {/* 日付：カレンダー入力（枠全体クリック＋中央にカレンダーアイコン） */}
            <div style={{ position: 'relative', flex: 1 }}>
              <input
                type="date"
                value={deadlineDate}
                onChange={(e) => setDeadlineDate(e.target.value)}
                required
                style={{
                  width: '100%',
                  padding: '0.5rem',
                  fontSize: '1rem',
                  // 未選択のときは文字色を透明にして「年/月/日」を消す
                  color: deadlineDate ? '#000' : 'transparent',
                  // 枠全体がクリック可能
                  boxSizing: 'border-box',
                }}
              />
              {/* 未選択のときだけ中央にカレンダーアイコンを表示 */}
              {!deadlineDate && (
                <div
                  style={{
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    pointerEvents: 'none', // これでクリックは全部input側に行く
                    fontSize: '1.2rem',
                    color: '#666',
                  }}
                >
                  📅
                </div>
              )}
            </div>

            {/* 時刻：時（1〜24）＋ 分（00 / 30） */}
            <select
              value={deadlineHour}
              onChange={(e) => setDeadlineHour(e.target.value)}
              style={{ width: '110px', padding: '0.5rem', fontSize: '1rem' }}
            >
              {Array.from({ length: 24 }, (_, i) => {
                const h = i + 1; // 1〜24
                const label = `${String(h).padStart(2, '0')}:00`;
                return (
                  <option key={h} value={h.toString()}>
                    {label}
                  </option>
                );
              })}
            </select>

            <select
              value={deadlineMinute}
              onChange={(e) => setDeadlineMinute(e.target.value)}
              style={{ width: '90px', padding: '0.5rem', fontSize: '1rem' }}
            >
              <option value="00">00</option>
              <option value="30">30</option>
            </select>
          </div>

          <p style={{ marginTop: '0.25rem', fontSize: '0.85rem', color: '#666' }}>
            ※0時締切の課題は、日付を1日前にして「24:00」で登録してください。
            （例：12/1 の 0:00 締切 → 11/30 の 24:00 として登録）
          </p>

        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          style={{
            padding: '0.75rem 1.5rem',
            fontSize: '1rem',
            backgroundColor: '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: isSubmitting ? 'not-allowed' : 'pointer',
          }}
        >
          {isSubmitting ? '作成中...' : '課題を追加'}
        </button>
      </form>
    </div>
  );
};

