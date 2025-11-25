import { useState, useEffect } from 'react';
import { NotificationSetting, NotificationSettingUpdate } from '../types';
import { settingsApi } from '../api/settings';

export const NotificationSettings: React.FC = () => {
  const [, setSetting] = useState<NotificationSetting | null>(null);
  const [offsets, setOffsets] = useState<number[]>([24, 3, 1]);
  const [digestTime, setDigestTime] = useState<string>('08:00');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const data = await settingsApi.getNotification();
      setSetting(data);
      setOffsets([...data.reminder_offsets_hours]);
      setDigestTime(data.daily_digest_time);
    } catch (error) {
      console.error('通知設定の取得に失敗しました:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddOffset = () => {
    setOffsets([...offsets, 1]);
  };

  const handleRemoveOffset = (index: number) => {
    setOffsets(offsets.filter((_, i) => i !== index));
  };

  const handleOffsetChange = (index: number, value: number) => {
    const newOffsets = [...offsets];
    newOffsets[index] = value;
    setOffsets(newOffsets);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const updateData: NotificationSettingUpdate = {
        reminder_offsets_hours: offsets.filter((o) => o > 0),
        daily_digest_time: digestTime,
      };
      await settingsApi.updateNotification(updateData);
      await loadSettings();
      alert('通知設定を保存しました');
    } catch (error) {
      console.error('通知設定の保存に失敗しました:', error);
      alert('通知設定の保存に失敗しました');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return <p>読み込み中...</p>;
  }

  return (
    <div style={{ marginBottom: '2rem', padding: '1.5rem', border: '1px solid #ddd', borderRadius: '8px' }}>
      <h2 style={{ marginTop: 0 }}>通知設定</h2>
      
      <div style={{ marginBottom: '1.5rem' }}>
        <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
          締切リマインド（何時間前に通知するか）
        </label>
        {offsets.map((offset, index) => (
          <div key={index} style={{ display: 'flex', alignItems: 'center', marginBottom: '0.5rem' }}>
            <input
              type="number"
              min="1"
              value={offset}
              onChange={(e) => handleOffsetChange(index, parseInt(e.target.value) || 1)}
              style={{ width: '100px', padding: '0.5rem', marginRight: '0.5rem' }}
            />
            <span>時間前</span>
            {offsets.length > 1 && (
              <button
                onClick={() => handleRemoveOffset(index)}
                style={{
                  marginLeft: '0.5rem',
                  padding: '0.25rem 0.5rem',
                  backgroundColor: '#dc3545',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                }}
              >
                削除
              </button>
            )}
          </div>
        ))}
        <button
          onClick={handleAddOffset}
          style={{
            marginTop: '0.5rem',
            padding: '0.5rem 1rem',
            backgroundColor: '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
        >
          時間を追加
        </button>
      </div>

      <div style={{ marginBottom: '1.5rem' }}>
        <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
          日次ダイジェスト送信時間
        </label>
        <input
          type="time"
          value={digestTime}
          onChange={(e) => setDigestTime(e.target.value)}
          style={{ padding: '0.5rem', fontSize: '1rem' }}
        />
      </div>

      <button
        onClick={handleSave}
        disabled={isSaving}
        style={{
          padding: '0.75rem 1.5rem',
          fontSize: '1rem',
          backgroundColor: '#28a745',
          color: 'white',
          border: 'none',
          borderRadius: '4px',
          cursor: isSaving ? 'not-allowed' : 'pointer',
        }}
      >
        {isSaving ? '保存中...' : '設定を保存'}
      </button>
    </div>
  );
};

