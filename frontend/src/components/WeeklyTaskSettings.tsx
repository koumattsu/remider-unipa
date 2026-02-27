// frontend/src/components/WeeklyTaskSettings.tsx

import { useState } from 'react';
import { WeeklyTask } from '../types';
import { weeklyTasksApi } from '../api/weeklyTasks';

interface WeeklyTaskSettingsProps {
  templates: WeeklyTask[];
  onTemplatesChanged: () => void;
}

type FormState = {
  title: string;
  memo: string;
  weekday: number; // 0=月〜6=日
  time_hour: number;
  time_minute: number;
  is_active: boolean;
};

const defaultForm: FormState = {
  title: '',
  memo: '',
  weekday: 0,
  time_hour: 24,
  time_minute: 0,
  is_active: true,
};

export const WeeklyTaskSettings: React.FC<WeeklyTaskSettingsProps> = ({
  templates,
  onTemplatesChanged,
}) => {
  const [form, setForm] = useState<FormState>(defaultForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleChange = (
    key: keyof FormState,
    value: string | number | boolean
  ) => {
    setForm((prev) => ({ ...prev, [key]: value as any }));
  };

  const resetForm = () => {
    setForm(defaultForm);
    setEditingId(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) {
      alert('タイトルは必須です');
      return;
    }

    // ✅ 壊れにくい補正:
    // - UI/他経路のバグで 00:00 が入ってきたら「24:00」として送る
    //   （backend の normalize_weekly_time(24:00→weekday+1の00:00) に必ず乗せる）
    const effectiveHour =
      form.time_hour === 0 && form.time_minute === 0 ? 24 : form.time_hour;

    const payload = {
      title: form.title.trim(),
      course_name: '__manual__',
      memo: form.memo,
      weekday: form.weekday,
      time_hour: effectiveHour,
      time_minute: form.time_minute,
      is_active: form.is_active,
    };

    try {
      setIsSubmitting(true);
      if (editingId == null) {
        await weeklyTasksApi.create(payload);
      } else {
        await weeklyTasksApi.update(editingId, payload);
      }
      resetForm();
      onTemplatesChanged();
    } catch (error) {
      console.error('毎週タスクの保存に失敗しました:', error);
      alert('毎週タスクの保存に失敗しました');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEditClick = (tpl: WeeklyTask) => {
    const minute = tpl.time_minute ?? 0;

    // ✅ 「前日24:00」扱いに戻すのは、00:00 のときだけ（00:30 等は巻き込まない）
    const isNormalized24 = tpl.time_hour === 0 && minute === 0;

    const uiWeekday = isNormalized24 ? (tpl.weekday + 6) % 7 : tpl.weekday;
    const uiHour = isNormalized24 ? 24 : (tpl.time_hour ?? 24);

    setEditingId(tpl.id);
    setForm({
      title: tpl.title,
      memo: tpl.memo || '',
      weekday: uiWeekday,
      time_hour: uiHour,
      time_minute: minute,
      is_active: tpl.is_active,
    });
  };

  const handleDeleteClick = async (tpl: WeeklyTask) => {
    if (!confirm(`"${tpl.title}" を削除しますか？`)) return;
    try {
      await weeklyTasksApi.delete(tpl.id);
      if (editingId === tpl.id) {
        resetForm();
      }
      onTemplatesChanged();
    } catch (error) {
      console.error('毎週タスクの削除に失敗しました:', error);
      alert('毎週タスクの削除に失敗しました');
    }
  };

  const weekdayLabels = ['月', '火', '水', '木', '金', '土', '日'];

  return (
    <div
      className="glass"
      style={{
        border: '1px solid rgba(255,255,255,.10)',
        borderRadius: 16,
        padding: '1rem',
        background: 'rgba(255,255,255,.06)',
        backdropFilter: 'blur(14px)',
        WebkitBackdropFilter: 'blur(14px)',
        color: 'rgba(255,255,255,.88)',
      }}
    >
      <h2 style={{ marginBottom: '0.75rem', fontSize: '1rem', fontWeight: 600 }}>
        毎週タスクを追加
      </h2>

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginBottom: '1rem' }}>
        <div>
          <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: 4 }}>
            タイトル *
          </label>
          <input
            type="text"
            value={form.title}
            onChange={(e) => handleChange('title', e.target.value)}
            className="glass-field"
            style={{ fontSize: '0.9rem' }}
          />
        </div>

        <div>
          <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: 4 }}>
            メモ
          </label>
          <textarea
            value={form.memo}
            onChange={(e) => handleChange('memo', e.target.value)}
            className="glass-field"
            style={{ minHeight: 80, fontSize: '0.9rem' }}
          />
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center' }}>
          
          <div>
            <span style={{ fontSize: '0.85rem', marginRight: 4 }}>曜日</span>
            <select
              value={form.weekday}
              onChange={(e) => handleChange('weekday', Number(e.target.value))}
              className="glass-field"
              style={{ width: 110, fontSize: '0.85rem' }}
            >
              {weekdayLabels.map((label, idx) => (
                <option key={idx} value={idx}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <span style={{ fontSize: '0.85rem', marginRight: 4 }}>時刻</span>
            <select
              value={form.time_hour}
              onChange={(e) => handleChange('time_hour', Number(e.target.value))}
              className="glass-field"
              style={{ width: 80, fontSize: '0.85rem', marginRight: 4 }}
            >
              {Array.from({ length: 24 }).map((_, idx) => {
                const h = idx + 1; // 1〜24
                return (
                  <option key={h} value={h}>
                    {String(h).padStart(2, '0')}
                  </option>
                );
              })}
            </select>
            :
            <select
              value={form.time_minute}
              onChange={(e) => handleChange('time_minute', Number(e.target.value))}
              className="glass-field"
              style={{ width: 80, fontSize: '0.85rem', marginLeft: 4 }}
            >
              {[0, 30].map((m) => (
                <option key={m} value={m}>
                  {String(m).padStart(2, '0')}
                </option>
              ))}
            </select>
          </div>

          <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.85rem' }}>
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => handleChange('is_active', e.target.checked)}
            />
            有効
          </label>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
          <button
            type="submit"
            disabled={isSubmitting}
            style={{
              padding: '0.45rem 0.9rem',
              fontSize: '0.9rem',
              borderRadius: 6,
              border: 'none',
              backgroundColor: '#2563eb',
              color: '#fff',
              cursor: isSubmitting ? 'not-allowed' : 'pointer',
            }}
          >
            {editingId == null ? '毎週タスクを追加' : '毎週タスクを更新'}
          </button>
          {editingId != null && (
            <button
              type="button"
              onClick={resetForm}
              style={{
                padding: '0.45rem 0.9rem',
                fontSize: '0.9rem',
                borderRadius: 6,
                background: 'transparent',
                border: '1px solid rgba(255,255,255,.25)',
                color: 'rgba(255,255,255,.75)',
                cursor: 'pointer',
              }}
            >
              キャンセル
            </button>
          )}
        </div>
      </form>

      {/* 一覧 */}
      <div
        style={{
          marginTop: '0.75rem',
          paddingTop: '0.75rem',
          borderTop: '1px solid rgba(255,255,255,.12)',
        }}
      >
        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontSize: '0.9rem',
          }}
        >
          <thead>
            <tr style={{ backgroundColor: 'rgba(255,255,255,.06)' }}>
              <th style={{ padding: '0.4rem', textAlign: 'left' }}>曜日</th>
              <th style={{ padding: '0.4rem', textAlign: 'left' }}>時刻</th>
              <th style={{ padding: '0.4rem', textAlign: 'left' }}>タイトル</th>
              <th style={{ padding: '0.4rem', textAlign: 'left' }}>有効</th>
              <th style={{ padding: '0.4rem', textAlign: 'left' }}>操作</th>
            </tr>
          </thead>
          
          <tbody>
              {templates.map((tpl) => {
              const minute = tpl.time_minute ?? 0;
              const isNormalized24 = tpl.time_hour === 0 && minute === 0;

              // ✅ 00:00 のときだけ「前日 24:00」表示（weekdayも -1）
              const weekdayIndex = isNormalized24 ? (tpl.weekday + 6) % 7 : tpl.weekday;

              // 時刻は 00:00 のときだけ 24 に見せる
              const hourDisplay = isNormalized24 ? 24 : (tpl.time_hour ?? 0);

              return (
                <tr key={tpl.id} style={{ borderTop: '1px solid rgba(255,255,255,.10)' }}>
                  <td style={{ padding: '0.4rem' }}>
                    {weekdayLabels[weekdayIndex]}
                  </td>
                  <td style={{ padding: '0.4rem' }}>
                    {String(hourDisplay).padStart(2, '0')}:
                    {String(tpl.time_minute ?? 0).padStart(2, '0')}
                  </td>
                  <td style={{ padding: '0.4rem' }}>{tpl.title}</td>
                  <td style={{ padding: '0.4rem' }}>
                    {tpl.is_active ? '有効' : '無効'}
                  </td>
                  <td style={{ padding: '0.4rem' }}>
                    <button
                      onClick={() => handleEditClick(tpl)}
                      style={{
                        padding: '0.25rem 0.6rem',
                        fontSize: '0.8rem',
                        borderRadius: 4,
                        background: 'rgba(255,255,255,.10)',
                        border: '1px solid rgba(255,255,255,.18)',
                        color: 'rgba(255,255,255,.9)',
                        backdropFilter: 'blur(6px)',
                        marginRight: 4,
                        cursor: 'pointer',
                      }}
                    >
                      編集
                    </button>
                    <button
                      onClick={() => handleDeleteClick(tpl)}
                      style={{
                        padding: '0.25rem 0.6rem',
                        fontSize: '0.8rem',
                        borderRadius: 4,
                        border: 'none',
                        backgroundColor: '#dc2626',
                        color: '#fff',
                        cursor: 'pointer',
                      }}
                    >
                      削除
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>

        </table>
      </div>
    </div>
  );
};
