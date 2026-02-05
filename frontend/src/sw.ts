// frontend/src/sw.ts
/// <reference lib="webworker" />

import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching'
import { clientsClaim } from 'workbox-core'

declare const self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: any
}

// ✅ 古いキャッシュを掃除（precacheの世代交代で残骸が残りにくい）
cleanupOutdatedCaches()

// ✅ injectManifest の注入ポイント
precacheAndRoute(self.__WB_MANIFEST)

// ✅ workbox推奨：トップレベルで claim（activate中に登録しない）
clientsClaim()

// ✅ 新SWを即反映（“デプロイしたのに画面が変わらない”対策の本丸）
self.addEventListener('install', () => {
  self.skipWaiting()
})

self.addEventListener('push', (event) => {
  let data: any = {}
  try {
    data = event.data ? event.data.json() : {}
  } catch {
    data = {}
  }
  const title = data.title || 'UNIPA Reminder'
  const body = data.body || '通知があります'
  const rawUrl = data.url || '/dashboard?tab=today'
  const url = new URL(rawUrl, self.registration.scope).toString()
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      data: {
        url,
        notification_id: data.notification_id ?? null,
        run_id: data.run_id ?? null,
      },
    })
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const rawUrl = (event.notification as any)?.data?.url || '/dashboard?tab=today'
  const url = new URL(rawUrl, self.registration.scope).toString()

  event.waitUntil(
    (async () => {
      try {
        const payload = {
          type: 'opened',
          notification_id: (event.notification as any)?.data?.notification_id ?? null,
          run_id: (event.notification as any)?.data?.run_id ?? null,
        }

        // ✅ 同一オリジンで確実に叩く（FastAPI側の router prefix に合わせる）
        const eventsUrl = new URL('/api/v1/notifications/webpush/events', self.registration.scope).toString()

        await fetch(eventsUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          credentials: 'include',
          keepalive: true,
        })
      } catch {}

      const allClients = await self.clients.matchAll({
        type: 'window',
        includeUncontrolled: true,
      })
      const target = new URL(url)

      for (const client of allClients) {
        try {
          const c = new URL(client.url)
          if (c.origin !== target.origin) continue
          // @ts-ignore
          if (client.focus) {
            // @ts-ignore
            await client.focus()
            // @ts-ignore
            if (client.url !== url && client.navigate) {
              // @ts-ignore
              await client.navigate(url)
            }
            return
          }
        } catch {}
      }

      if (self.clients.openWindow) return self.clients.openWindow(url)
    })()
  )
})
