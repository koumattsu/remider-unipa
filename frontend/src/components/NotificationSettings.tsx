// frontend/src/components/NotificationSettings.tsx

import { useState, useEffect } from 'react';
import { NotificationSetting, NotificationSettingUpdate } from '../types';
import { settingsApi } from '../api/settings';

const NOTIFICATION_STORAGE_KEY = 'unipa_notification_settings_v1';

type StoredNotificationSettings = {
  enableMorning: boolean;
  dailyDigestTime: string;
  reminderOffsetsHours: number[];
};

// 5:00〜10:00 を30分刻みで生成
const MORNING_TIME_OPTIONS = Array.from({ length: 11 }, (_, i) => {
  const totalMinutes = 5 * 60 + i * 30; // 5:00スタート
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
});

interface ToggleSwitchProps {
  checked: boolean;
  onChange: () => void;
}

// ちょい近未来寄りのトグル
const ToggleSwitch: React.FC<ToggleSwitchProps> = ({ checked, onChange }) => (
  <div
    onClick={onChange}
    style={{
      width: 50,
      height: 26,
      borderRadius: 9999,
      padding: 3,
      background: checked
        ? 'linear-gradient(90deg, #00d4ff, #007aff)'
        : '#ccc',
      boxShadow: checked
        ? '0 0 10px rgba(0, 212, 255, 0.7)'
        : 'inset 0 0 4px rgba(0,0,0,0.2)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: checked ? 'flex-end' : 'flex-start',
      cursor: 'pointer',
      transition:
        'background 0.2s ease, box-shadow 0.2s ease, justify-content 0.2s ease',
    }}
  >
    <div
      style={{
        width: 20,
        height: 20,
        borderRadius: '50%',
        background: checked
          ? 'radial-gradient(circle at 30% 30%, #ffffff, #e0f7ff)'
          : '#fff',
        boxShadow: '0 2px 4px rgba(0,0,0,0.3)',
      }}
    />
  </div>
);

export const NotificationSettings: React.FC = () => {
  const [, setSetting] = useState<NotificationSetting | null>(null);

  // 時間前通知（例: [3,5,7]）
  const [offsets, setOffsets] = useState<number[]>([3]);

  // 朝通知の時刻
  const [digestTime, setDigestTime] = useState<string>('08:00');

  // 朝通知 ON / OFF
  const [enableMorning, setEnableMorning] = useState<boolean>(true);

  // 3時間前通知 ON / OFF
  const [enableThreeHours, setEnableThreeHours] = useState<boolean>(true);

  // プッシュ通知 ON / OFF
  const [enableWebpush, setEnableWebpush] = useState<boolean>(false);

  // ブラウザ許可状態
  const [permission, setPermission] = useState<NotificationPermission>(
    typeof Notification !== 'undefined' ? Notification.permission : 'default'
  );

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const data = await settingsApi.getNotification();
      setSetting(data);

      setEnableWebpush(data.enable_webpush ?? false);

      const hours = [...data.reminder_offsets_hours];

      // 朝通知時刻：options にない値なら "08:00" にフォールバック
      const time = MORNING_TIME_OPTIONS.includes(data.daily_digest_time)
        ? data.daily_digest_time
        : '08:00';

      // 朝通知 ON/OFF（未定義なら true 扱い）
      const enableMorningValue =
        data.enable_morning_notification !== undefined
          ? data.enable_morning_notification
          : true;

      setOffsets(hours);
      setDigestTime(time);
      setEnableThreeHours(hours.includes(3));
      setEnableMorning(enableMorningValue);

      // 👇 ここで localStorage にも保存しておく
      try {
        const stored: StoredNotificationSettings = {
          enableMorning: enableMorningValue,
          dailyDigestTime: time,
          reminderOffsetsHours: hours,
        };
        window.localStorage.setItem(
          NOTIFICATION_STORAGE_KEY,
          JSON.stringify(stored)
        );
      } catch (e) {
        console.warn('localStorage への保存に失敗しました:', e);
      }
    } catch (error) {
      console.error('通知設定の取得に失敗しました:', error);
    } finally {
      setIsLoading(false);
    }
  };


  const handleAddOffset = () => {
    setOffsets((prev) => [...prev, 1]);
  };

  const handleRemoveOffset = (index: number) => {
    setOffsets((prev) => {
      const others = prev.filter((o) => o !== 3);
      const newOthers = others.filter((_, i) => i !== index);

      const result: number[] = [];

      // もともと 3h があれば保持
      if (prev.includes(3)) {
        result.push(3);
      }

      for (const o of newOthers) {
        if (!result.includes(o)) {
          result.push(o);
        }
      }

      return result;
    });
  };

  const handleOffsetChange = (index: number, value: number) => {
    setOffsets((prev) => {
      const safeValue = value > 0 ? value : 1;

      const others = prev.filter((o) => o !== 3);
      const newOthers = [...others];
      newOthers[index] = safeValue;

      const result: number[] = [];

      if (prev.includes(3)) {
        result.push(3);
      }

      for (const o of newOthers) {
        if (!result.includes(o)) {
          result.push(o);
        }
      }

      return result;
    });
  };

  const handleSave = async () => {
    setIsSaving(true);

    try {
      let newOffsets = offsets.filter((o) => o > 0);

      // 3時間前 OFF のときは 3 を削除
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
        enable_morning_notification: enableMorning,
        enable_webpush: enableWebpush,
      };

      // 👇 localStorage にも保存しておく
      try {
        const stored: StoredNotificationSettings = {
          enableMorning,
          dailyDigestTime: digestTime,
          reminderOffsetsHours: newOffsets,
        };
        window.localStorage.setItem(
          NOTIFICATION_STORAGE_KEY,
          JSON.stringify(stored)
        );
      } catch (e) {
        console.warn('localStorage への保存に失敗しました:', e);
      }


      await settingsApi.updateNotification(updateData);
      await loadSettings();

      // 🔔 成功したらフロント側キャッシュも更新（loadSettings 内でもやっているけど念のため）
      if (typeof window !== 'undefined') {
        const stored = {
          enableMorning,
          dailyDigestTime: digestTime,
          reminderOffsetsHours: newOffsets,
        };
        window.localStorage.setItem(
          NOTIFICATION_STORAGE_KEY,
          JSON.stringify(stored)
        );
      }

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

  // 3時間前(3h)以外のオフセットだけを表示用に取り出す
  const otherOffsets = offsets.filter((o) => o !== 3);

  return (
    <div
      style={{
        marginBottom: '2rem',
        padding: '1.5rem',
        border: '1px solid #ddd',
        borderRadius: '8px',
      }}
    >
      <h2 style={{ marginTop: 0 }}>通知設定</h2>

      {/* プッシュ通知 ON / OFF */}
      <div
        style={{
          marginBottom: '1.5rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div>
          <div style={{ fontWeight: 'bold', marginBottom: '0.25rem' }}>
            プッシュ通知
          </div>
          <div style={{ fontSize: '0.9rem', color: '#666' }}>
            アプリを開いていなくても締切前に通知します
          </div>
        </div>

        <ToggleSwitch
          checked={enableWebpush}
          onChange={() => {
            const next = !enableWebpush;
            setEnableWebpush(next);

            if (next) {
              // ON にした瞬間にブラウザ許可状態を確認
              if (typeof Notification !== 'undefined') {
                setPermission(Notification.permission);
              }
            }
          }}
        />
      </div>

      {enableWebpush && permission === 'default' && (
        <div
          style={{
            marginBottom: '1rem',
            padding: '0.75rem',
            background: '#f8f9fa',
            border: '1px solid #ddd',
            borderRadius: '6px',
            fontSize: '0.9rem',
          }}
        >
          通知を受け取るには、ブラウザの許可が必要です。
          <button
            style={{
              marginLeft: '0.75rem',
              padding: '0.4rem 0.75rem',
              borderRadius: '4px',
              border: 'none',
              background: '#007bff',
              color: '#fff',
              cursor: 'pointer',
            }}
            onClick={async () => {
              const result = await Notification.requestPermission();
              setPermission(result);
            }}
          >
            許可する
          </button>
        </div>
      )}

      {enableWebpush && permission === 'denied' && (
        <div
          style={{
            marginBottom: '1rem',
            color: '#dc3545',
            fontSize: '0.9rem',
          }}
        >
          通知がブロックされています。ブラウザの設定から許可してください。
        </div>
      )}
        {enableWebpush && (
          <>
            {/* 朝通知：時間セレクト + トグル */}
            <div
              style={{
                marginBottom: '1.5rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div style={{ fontWeight: 'bold', marginBottom: '0.25rem' }}>
                  朝通知
                </div>
                <div style={{ fontSize: '0.9rem', color: '#666' }}>
                  毎朝のまとめ通知（5:00〜10:00 の間で設定）
                </div>
              </div>

              <div
                style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}
              >
                {/* 朝通知時刻セレクト：5:00〜10:00 を30分刻み */}
                <select
                  value={digestTime}
                  onChange={(e) => setDigestTime(e.target.value)}
                  style={{ padding: '0.4rem 0.6rem', fontSize: '0.95rem' }}
                >
                  {MORNING_TIME_OPTIONS.map((time) => (
                    <option key={time} value={time}>
                      {time}
                    </option>
                  ))}
                </select>

                <ToggleSwitch
                  checked={enableMorning}
                  onChange={() => setEnableMorning(!enableMorning)}
                />
              </div>
            </div>

            {/* 3時間前通知：トグル */}
            <div
              style={{
                marginBottom: '1.5rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div style={{ fontWeight: 'bold', marginBottom: '0.25rem' }}>
                  締切3時間前通知
                </div>
                <div style={{ fontSize: '0.9rem', color: '#666' }}>
                  締切の3時間前にリマインド
                </div>
              </div>

              <ToggleSwitch
                checked={enableThreeHours}
                onChange={() => setEnableThreeHours(!enableThreeHours)}
              />
            </div>

            {/* その他の時間設定 */}
            <div style={{ marginBottom: '1.5rem' }}>
              <label
                style={{
                  display: 'block',
                  marginBottom: '0.5rem',
                  fontWeight: 'bold',
                }}
              >
                その他のリマインド時間（自由設定）
              </label>

              {otherOffsets.map((offset, index) => (
                <div
                  key={index}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    marginBottom: '0.5rem',
                  }}
                >
                  <input
                    type="number"
                    min="1"
                    value={offset}
                    onChange={(e) =>
                      handleOffsetChange(
                        index,
                        parseInt(e.target.value, 10) || 1
                      )
                    }
                    style={{
                      width: '100px',
                      padding: '0.5rem',
                      marginRight: '0.5rem',
                    }}
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
          </>
      )}
    </div>
  );
};
