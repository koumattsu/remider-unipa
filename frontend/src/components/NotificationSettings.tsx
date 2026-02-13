// frontend/src/components/NotificationSettings.tsx

import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { NotificationSetting, NotificationSettingUpdate } from '../types';
import { settingsApi } from '../api/settings';

const NOTIFICATION_STORAGE_KEY = 'unipa_notification_settings_v1';

function urlBase64ToUint8Array(base64String: string) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

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
  disabled?: boolean;
}

const ToggleSwitch: React.FC<ToggleSwitchProps> = ({ checked, onChange, disabled }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
    <div
      onClick={() => {
        if (disabled) return;
        onChange();
      }}
      role="switch"
      aria-checked={checked}
      aria-disabled={!!disabled}
      style={{
        width: 56,
        height: 30,
        borderRadius: 9999,
        padding: 3,
        background: disabled
          ? '#e5e5e5'
          : checked
          ? 'linear-gradient(90deg, #00d4ff, #007aff)'
          : '#ccc',
        boxShadow: disabled
          ? 'inset 0 0 4px rgba(0,0,0,0.12)'
          : checked
          ? '0 0 10px rgba(0, 212, 255, 0.7)'
          : 'inset 0 0 4px rgba(0,0,0,0.2)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: checked ? 'flex-end' : 'flex-start',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.7 : 1,
        transition:
          'background 0.2s ease, box-shadow 0.2s ease, justify-content 0.2s ease',
        userSelect: 'none',
      }}
    >
      <div
        style={{
          width: 22,
          height: 22,
          borderRadius: '50%',
          background: checked
            ? 'radial-gradient(circle at 30% 30%, #ffffff, #e0f7ff)'
            : '#fff',
          boxShadow: '0 2px 4px rgba(0,0,0,0.3)',
        }}
      />
    </div>

    {/* ✅ 状態が一瞬で分かるラベル */}
    <span style={{ fontSize: 12, fontWeight: 800, opacity: disabled ? 0.6 : 0.85 }}>
      {checked ? 'ON' : 'OFF'}
    </span>
  </div>
);

export const NotificationSettings: React.FC = () => {
  const [, setSetting] = useState<NotificationSetting | null>(null);

  // TODO: 将来 backend から plan を受け取って差し替える
  const isPro = false; // 無料運用中は false 固定

  // 無料ユーザー：時間前通知は 1h のみ（ON/OFF）
  const [offsets, setOffsets] = useState<number[]>([1]);

  // 朝通知の時刻
  const [digestTime, setDigestTime] = useState<string>('08:00');

  // 朝通知 ON / OFF
  const [enableMorning, setEnableMorning] = useState<boolean>(true);

  // 1時間前通知 ON / OFF（無料のメイン）
  const [enableOneHour, setEnableOneHour] = useState<boolean>(true);

  // プッシュ通知 ON / OFF
  const [enableWebpush, setEnableWebpush] = useState<boolean>(false);

  // ブラウザ許可状態
  const [permission, setPermission] = useState<NotificationPermission>(
    typeof Notification !== 'undefined' ? Notification.permission : 'default'
  );

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  const [pushSupported, setPushSupported] = useState(false);
  const [pushEnabled, setPushEnabled] = useState(false);
  const [pushError, setPushError] = useState<string | null>(null);
  const [pushTestResult, setPushTestResult] = useState<string | null>(null);

  useEffect(() => {
    const supported =
      'serviceWorker' in navigator &&
      'PushManager' in window &&
      'Notification' in window;

    setPushSupported(supported);

    (async () => {
      if (!supported) return;
      try {
        const reg = await navigator.serviceWorker.getRegistration();
        if (!reg) {
          setPushEnabled(false);
          return;
        }
        const sub = await reg.pushManager.getSubscription();
        setPushEnabled(!!sub);
      } catch {
        setPushEnabled(false);
      }
    })();
  }, []);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const data = await settingsApi.getNotification();
      setSetting(data);

      setEnableWebpush(data.enable_webpush ?? false);

      // 無料ユーザー：許可するのは 1h のみ
      const hours = [...(data.reminder_offsets_hours ?? [])].filter((h) => h === 1);

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
      setEnableOneHour(hours.includes(1));
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
    setOffsets((prev) => {
      // 1時間前（ベース）があるか
      const hasBase = prev.includes(1);

      // 1以外（＝その他）
      const others = prev.filter((o) => o !== 1);

      // デフォルトで「2時間前」を追加（被らない安全な値）
      const next = 2;

      const result: number[] = [];
      if (hasBase) result.push(1);
      result.push(...others, next);

      return result;
    });
  };

  const enableWebPush = async () => {
    setPushError(null);

    if (!pushSupported) {
      setPushError('このブラウザは Web Push に対応していません');
      return;
    }

    try {
      // 1) SW 登録（public/sw.js）
      const reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' });

      // ✅ 追加：activate まで待つ（push を確実に拾う）
      await navigator.serviceWorker.ready;

      // 2) 通知許可
      const perm = await Notification.requestPermission();
      // ✅ 追加：stateも更新（UIのズレ防止）
      setPermission(perm);

      if (perm !== 'granted') {
        setPushError('通知が許可されませんでした（ブラウザ設定を確認してください）');
        return;
      }

      // 3) VAPID 公開鍵を backend から取得（←これが抜けてた）
      const { data } = await apiClient.get('/notifications/webpush/public-key');
      const publicKey: string | undefined = data?.publicKey;
      if (!publicKey) {
        setPushError('VAPID 公開鍵の取得に失敗しました');
        return;
      }

      // 4) subscribe（既存があれば再利用）
      const existing = await reg.pushManager.getSubscription();
      const sub =
        existing ??
        (await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(publicKey),
        }));

      const json = sub.toJSON();
      const endpoint = sub.endpoint;
      const p256dh = json?.keys?.p256dh;
      const auth = json?.keys?.auth;

      if (!endpoint || !p256dh || !auth) {
        setPushError('subscription の形式が不正です');
        return;
      }

      await apiClient.post('/notifications/webpush/subscriptions', {
        endpoint,
        keys: { p256dh, auth },
        user_agent: navigator.userAgent,
        device_label: 'primary', // 例: 端末名UIがまだなら固定でもOK（<=64）
      });

      // 6) ✅ ユーザー設定(enable_webpush)も即ONにして、debug-send が sent=0 にならないようにする
      try {
        if (!enableWebpush) {
          setEnableWebpush(true);
        }
        const newOffsets = enableOneHour ? [1] : [];
        const updateData: NotificationSettingUpdate = {
          reminder_offsets_hours: newOffsets,
          daily_digest_time: digestTime,
          enable_morning_notification: enableMorning,
          enable_webpush: true,
        };
        await settingsApi.updateNotification(updateData);
      } catch (e) {
        // ここで失敗しても購読自体はできているので、pushEnabled は true にする
        console.warn('enable_webpush の保存に失敗しました:', e);
      }
      setPushEnabled(true);
    } catch (e: any) {
      setPushError(e?.message ?? 'Web Push の有効化に失敗しました');
    }
  };

  const disableWebPush = async () => {
    setPushError(null);

    if (!pushSupported) return;

    try {
      const reg = await navigator.serviceWorker.getRegistration();
      if (!reg) {
        setPushEnabled(false);
        return;
      }
      const sub = await reg.pushManager.getSubscription();
      if (!sub) {
        setPushEnabled(false);
        return;
      }

      // backend 側も削除（by-endpoint を使う）
      await apiClient.delete('/notifications/webpush/subscriptions/by-endpoint', {
        params: { endpoint: sub.endpoint },
      });
      await sub.unsubscribe();
      setPushEnabled(false);
    } catch (e: any) {
      setPushError(e?.message ?? 'Web Push の解除に失敗しました');
    }
  };

  const testWebPush = async () => {
    setPushTestResult(null);
      setPushError(null);

      try {
        const res = await apiClient.post('/notifications/webpush/debug-send');
        const sent = res.data?.sent ?? 0;
        const failed = res.data?.failed ?? 0;
        const deactivated = res.data?.deactivated ?? 0;
        setPushTestResult(
          `debug-send: sent=${sent}, failed=${failed}, deactivated=${deactivated}`
        );
      } catch (e: any) {
        const status = e?.response?.status;
        setPushTestResult(null);
        setPushError(
          `debug-send failed${status ? ` (${status})` : ''}: ${
            e?.message ?? 'unknown error'
          }`
        );
      }
    };

  
  const handleRemoveOffset = (index: number) => {
    setOffsets((prev) => {
      const hasBase = prev.includes(1);
      const others = prev.filter((o) => o !== 1);
      const newOthers = others.filter((_, i) => i !== index);

      const result: number[] = [];
      if (hasBase) result.push(1);
      for (const o of newOthers) {
        if (!result.includes(o)) result.push(o);
      }
      return result;
    });
  };

  const handleOffsetChange = (index: number, value: number) => {
    setOffsets((prev) => {
      const safeValue = value > 0 ? value : 1;
      const hasBase = prev.includes(1);
      const others = prev.filter((o) => o !== 1);
      const newOthers = [...others];
      newOthers[index] = safeValue;

      const result: number[] = [];

      if (hasBase) result.push(1);

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
      // 無料ユーザー：1hのみON/OFF
      const newOffsets = enableOneHour ? [1] : [];
      
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

  // 有料ユーザー向け：1h(無料のメイン)以外を「その他」に回す
  // ※ isPro=false でも TS 的に otherOffsets は必要（JSXで参照するため）
  const otherOffsets = offsets.filter((o) => o !== 1);

  // 無料ユーザーは 1h のみ
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
            通知
          </div>
          <div style={{ fontSize: '0.9rem', color: '#666' }}>
            アプリを開いていなくても締切前に通知します
          </div>
        </div>

        <ToggleSwitch
          checked={enableWebpush}
          onChange={async () => {
            const next = !enableWebpush;
            setEnableWebpush(next);

            // ON のときは許可状態を見るだけ（購読ボタン側で enableWebPush() が動く）
            if (next) {
              if (typeof Notification !== 'undefined') {
                setPermission(Notification.permission);
              }
              return;
            }

            // ✅ OFF のときは「ボタンが消えても確実に保存」するため即保存
            setIsSaving(true);
            try {
              const newOffsets = enableOneHour ? [1] : [];
              const updateData: NotificationSettingUpdate = {
                reminder_offsets_hours: newOffsets,
                daily_digest_time: digestTime,
                enable_morning_notification: enableMorning,
                enable_webpush: false,
              };

              // localStorage も更新
              try {
                const stored: StoredNotificationSettings = {
                  enableMorning,
                  dailyDigestTime: digestTime,
                  reminderOffsetsHours: newOffsets,
                };
                window.localStorage.setItem(NOTIFICATION_STORAGE_KEY, JSON.stringify(stored));
              } catch (e) {
                console.warn('localStorage への保存に失敗しました:', e);
              }

              await settingsApi.updateNotification(updateData);
            } catch (e) {
              console.error('enable_webpush OFF の保存に失敗しました:', e);
              alert('通知OFFの保存に失敗しました');
              // 失敗したら見た目だけOFFになって事故るので戻す（安全側）
              setEnableWebpush(true);
            } finally {
              setIsSaving(false);
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
          <hr style={{ margin: '1rem 0' }} />

          <div style={{ display: 'grid', gap: '0.65rem' }}>
            {/* ✅ 見出し：左 端末通知 / 右 トグル */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 12,
              }}
            >
              <div style={{ fontWeight: 800 }}>端末通知</div>

              <ToggleSwitch
                checked={pushEnabled}
                disabled={!pushSupported || permission !== 'granted'}
                onChange={() => {
                  if (pushEnabled) {
                    disableWebPush();
                  } else {
                    enableWebPush();
                  }
                }}
              />
            </div>

            {/* ✅ サブ説明（白い長方形は作らない） */}
            <div style={{ fontSize: '0.9rem', color: 'rgba(255,255,255,0.75)' }}>
              {pushEnabled ? 'この端末は購読済みです' : 'この端末は未購読です'}
            </div>

            {!pushSupported && (
              <div style={{ fontSize: '0.9rem', opacity: 0.8 }}>
                このブラウザは Web Push に対応していません（iPhone は「ホームに追加」したPWAで有効になることがあります）
              </div>
            )}

            {pushError && <div style={{ fontSize: '0.9rem' }}>⚠️ {pushError}</div>}

            {/* ✅ テスト送信（大ボタンのまま） */}
            <button
              onClick={testWebPush}
              disabled={!pushEnabled || permission !== 'granted'}
              style={{
                marginTop: 6,
                padding: '0.85rem 1.1rem',
                fontSize: '1rem',
                fontWeight: 800,
                borderRadius: 12,
                border: 'none',
                cursor: (!pushEnabled || permission !== 'granted') ? 'not-allowed' : 'pointer',
                background:
                  (!pushEnabled || permission !== 'granted')
                    ? '#d7d7d7'
                    : 'linear-gradient(90deg, #00d4ff, #007aff)',
                color: '#fff',
                boxShadow:
                  (!pushEnabled || permission !== 'granted')
                    ? 'none'
                    : '0 8px 20px rgba(0, 122, 255, 0.25)',
              }}
            >
              テスト送信
            </button>

            {pushTestResult && (
              <div style={{ fontSize: '0.85rem', opacity: 0.75 }}>
                {pushTestResult}
              </div>
            )}

            {permission !== 'granted' && (
              <div style={{ fontSize: '0.85rem', opacity: 0.75 }}>
                先にブラウザの通知許可を「許可」にしてください（上の「許可する」ボタン）。
              </div>
            )}
          </div>
        </>
      )}
      {enableWebpush && (
          <>
            {/* 朝通知：時間セレクト + トグル */}
            <div
              style={{
                marginTop: '1.2rem', 
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

            {/* 1時間前通知：トグル（無料） */}
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
                  事前通知
                </div>
                <div style={{ fontSize: '0.9rem', color: '#666' }}>
                  締切の約1時間前に通知します
                </div>
              </div>

              <ToggleSwitch
                checked={enableOneHour}
                onChange={() => setEnableOneHour(!enableOneHour)}
              />
            </div>

            {/* その他の時間設定（有料のみ） */}
            {isPro && (
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
                        handleOffsetChange(index, parseInt(e.target.value, 10) || 1)
                      }
                      style={{
                        width: '100px',
                        padding: '0.5rem',
                        marginRight: '0.5rem',
                      }}
                    />
                    <span>時間前</span>

                    <button
                      type="button"
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
                  type="button"
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
            )}

            <button
              type="button"
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
