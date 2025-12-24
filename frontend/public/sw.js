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
  const url = data.url || '/#/dashboard?tab=today';

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      data: { url },
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification?.data?.url || '/#/dashboard?tab=today';

  event.waitUntil(
    (async () => {
      const allClients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      // 既存タブがあればそこへ
      for (const client of allClients) {
        if ('focus' in client) {
          client.navigate(url);
          return client.focus();
        }
      }
      // なければ新規
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })()
  );
});
