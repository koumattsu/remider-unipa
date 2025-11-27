import { useState, useEffect } from 'react';
import { NotificationSetting, NotificationSettingUpdate } from '../types';
import { settingsApi } from '../api/settings';

export const NotificationSettings: React.FC = () => {
  const [, setSetting] = useState<NotificationSetting | null>(null);

  // 時間前通知（例: [3,5,7]）
  const [offsets, setOffsets] = useState<number[]>([3]);

  // 朝通知の時刻
  const [digestTime, setDigestTime] = useState<string>('08:00');

  // ✅ 朝通知 ON / OFF
  const [enableMorning, setEnableMorning] = useState<boolean>(true);

  // ✅ 3時間前通知 ON / OFF
  const [enableThreeHours, setEnableThreeHours] = useState<boolean>(true);

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const data = await settingsApi.getNotification();
      setSetting(data);

      const hours = [...data.reminder_offsets_hours];
      setOffsets(hours);

      setDigestTime(data.daily_digest_time);

      // 3時間前があれば ON
      setEnableThreeHours(hours.includes(3));

      // 朝通知があれば ON（なければ true にする）
      setEnableMorning(
        data.enable_morning_notification !== undefined
          ? data.enable_morning_notification
          : true
      );

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
    const newOffsets = offsets.filter((_, i) => i !== index);
    setOffsets(newOffsets);
  };

  const handleOffsetChange = (index: number, value: number) => {
    const newOffsets = [...offsets];
    newOffsets[index] = value;
    setOffsets(newOffsets);
  };

  const handleSave = async () => {
    setIsSaving(true);

    try {
      let newOffsets = offsets.filter((o) => o > 0);

      // ✅ 3時間前 OFF のときは 3 を削除
      if (!enableThreeHours) {
        newOffsets = newOffsets.filter((o) => o !== 3);
      } else {
        if (!newOffsets.includes(3)) {
          newOffsets.push(3);
        }
      }

      const updateData: NotificationSettingUpdate = {
        reminder_offsets_hours: newOffsets,
        daily_digest_time: digestTime,

        // ✅ 朝通知 ON / OFF
        enable_morning_notification: enableMorning,
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

      {/* ✅ 朝8時通知 ON / OFF */}
      <div style={{ marginBottom: '1.5rem' }}>
        <label style={{ fontWeight: 'bold', marginRight: '1rem' }}>
          朝通知 (8:00)
        </label>
        <input
          type="checkbox"
          checked={enableMorning}
          onChange={() => setEnableMorning(!enableMorning)}
        />
      </div>

      {/* ✅ 3時間前通知 ON / OFF */}
      <div style={{ marginBottom: '1.5rem' }}>
        <label style={{ fontWeight: 'bold', marginRight: '1rem' }}>
          締切3時間前通知
        </label>
        <input
          type="checkbox"
          checked={enableThreeHours}
          onChange={() => setEnableThreeHours(!enableThreeHours)}
        />
      </div>

      {/* その他の時間設定 */}
      <div style={{ marginBottom: '1.5rem' }}>
        <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
          その他のリマインド時間（自由設定）
        </label>

        {offsets
          .filter((o) => o !== 3)
          .map((offset, index) => (
          <div key={index} style={{ display: 'flex', alignItems: 'center', marginBottom: '0.5rem' }}>
            <input
              type="number"
              min="1"
              value={offset}
              onChange={(e) => handleOffsetChange(index, parseInt(e.target.value) || 1)}
              style={{ width: '100px', padding: '0.5rem', marginRight: '0.5rem' }}
            />
            <span>時間前</span>

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

      {/* 朝通知時刻 */}
      <div style={{ marginBottom: '1.5rem' }}>
        <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
          朝通知の時刻
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
