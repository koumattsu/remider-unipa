// frontend/public/sw.js

self.addEventListener('push', (event) => {
  // payload は JSON を想定（無い場合もある）
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = {};
  }

  const title = data.title || 'UNIPA Reminder';
  const body = data.body || '通知があります';
  // ✅ scope基準で絶対URL化（PWA/複数タブでも壊れにくい）
  const rawUrl = data.url || '/dashboard?tab=today';
  const url = new URL(rawUrl, self.registration.scope).toString();

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      data: {
        url,
        // ✅ クリックを観測するための識別子（payloadに入ってくる想定）
        notification_id: data.notification_id ?? null,
        run_id: data.run_id ?? null,
      },
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const rawUrl = event.notification?.data?.url || '/dashboard?tab=today';
  const url = new URL(rawUrl, self.registration.scope).toString();

  event.waitUntil(
    (async () => {
      // ✅ クリック（opened）を backend に記録（最小）
      try {
        const payload = {
          type: 'opened',
          notification_id: event.notification?.data?.notification_id ?? null,
          run_id: event.notification?.data?.run_id ?? null,
          opened_at: new Date().toISOString(),
        };
        await fetch('/api/v1/webpush/events', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          // cookieセッション運用なら付ける（同一origin前提）
          credentials: 'include',
          // SWでの送信を落としにくくする（対応ブラウザのみ）
          keepalive: true,
        });
      } catch (e) {
        // 観測失敗はUXに影響させない
      }

      const allClients = await self.clients.matchAll({
        type: 'window',
        includeUncontrolled: true,
      });
      const target = new URL(url);
      // ✅ 既存タブ（同一origin）があればそこで開く
      for (const client of allClients) {
        try {
          const c = new URL(client.url);
          if (c.origin !== target.origin) continue;
          if ('focus' in client) {
            await client.focus();
            // navigate は同一originならOK。現在URLが違う時だけ遷移
            if (client.url !== url && 'navigate' in client) {
              await client.navigate(url);
            }
            return;
          }
        } catch (e) {
          // ignore
        }
      }
      // ✅ なければ新規
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })()
  );
});
