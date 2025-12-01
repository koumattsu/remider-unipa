// frontend/src/components/TaskForm.tsx

import { useState } from 'react';
import { TaskCreate } from '../types';
import { tasksApi } from '../api/tasks';

interface TaskFormProps {
  onTaskCreated: () => void;
}

export const TaskForm: React.FC<TaskFormProps> = ({ onTaskCreated }) => {
  const [formData, setFormData] = useState<Omit<TaskCreate, 'deadline'>>({
    title: '',
    course_name: '',
    memo: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [deadlineDate, setDeadlineDate] = useState('');   // 例: "2025-11-30"
  const [deadlineHour, setDeadlineHour] = useState('24'); // "1"〜"24"、デフォルト24時


    const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  setIsSubmitting(true);

  try {
    if (!deadlineDate) {
      alert('締切日を選択してください');
      setIsSubmitting(false);
      return;
    }

    const hourNum = Number(deadlineHour); // 1〜24
    let dateObj = new Date(deadlineDate); // 選択した日付の 00:00

    if (hourNum === 24) {
      // 24時 → 翌日の 00:00
      dateObj.setDate(dateObj.getDate() + 1);
      dateObj.setHours(0, 0, 0, 0);
    } else {
      // それ以外 → その日の hourNum:00
      dateObj.setHours(hourNum, 0, 0, 0);
    }

    const year = dateObj.getFullYear();
    const month = String(dateObj.getMonth() + 1).padStart(2, '0');
    const day = String(dateObj.getDate()).padStart(2, '0');
    const hour = String(dateObj.getHours()).padStart(2, '0');
    const minute = String(dateObj.getMinutes()).padStart(2, '0');
    const deadlineStr = `${year}-${month}-${day}T${hour}:${minute}`;

    await tasksApi.create({
      ...formData,
      title: formData.title.trim(),
      course_name: formData.course_name?.trim() || '',
      memo: formData.memo?.trim() || '',
      deadline: deadlineStr,
    });

    // フォームをリセット
    setFormData({
      title: '',
      course_name: '',
      memo: '',
    });
    setDeadlineDate('');
    setDeadlineHour('24');

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

            {/* 時間：1〜24時セレクト（デフォルト24時） */}
            <select
              value={deadlineHour}
              onChange={(e) => setDeadlineHour(e.target.value)}
              style={{ width: '120px', padding: '0.5rem', fontSize: '1rem' }}
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

