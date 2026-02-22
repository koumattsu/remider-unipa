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
  const sanitizeBody = (s: string) => {
    if (!s) return s
    // ✅ 内部識別子 __manual__ を通知表示から除去
    // 例: "(__manual__/ 02/11 23:00)" -> "(02/11 23:00)" に寄せる
    let out = s
      .replace(/\(\s*__manual__\s*\/\s*/g, '(')
      .replace(/__manual__/g, '')
      .replace(/\(\s*\/\s*/g, '(')        // 念のため "( / xx" を潰す
      .replace(/\(\s*\)/g, '')            // 空カッコ除去
      .replace(/[ \t]{2,}/g, ' ')         // 連続スペース整理
      .trim()
    return out
  }

  const title = data.title || 'DueFlow'
  const body = sanitizeBody(data.body || '通知があります')
  const rawUrl = data.deep_link || data.url || '/#/dashboard?tab=today'
  const normalized = normalizeToHashUrl(rawUrl)
  const url = new URL(normalized, self.registration.scope).toString()
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      data: {
        url,
        notification_id: data.notification_id ?? null,
        run_id: data.run_id ?? null,
        // ✅ opened 記録のSSOTキー（欠けると backend が 400 になる）
        event_token: data.event_token ?? null,
      },
    })
  )
})

// ✅ HashRouter防波堤：どんなurlが来ても "/#/..." に寄せる
const normalizeToHashUrl = (raw: string) => {
  const s = String(raw || '').trim()
  if (!s) return '/#/dashboard?tab=today'

  // すでに hash router 形式ならそのまま
  if (s.includes('#/')) return s

  // absolute URL の場合
  if (s.startsWith('http://') || s.startsWith('https://')) {
    try {
      const u = new URL(s)
      // hash が無いなら "#/path?query" を入れる
      if (!u.hash) {
        u.hash = u.pathname + u.search // "#/dashboard?tab=today"
        u.pathname = '/'
        u.search = ''
      }
      return u.toString()
    } catch {
      // 失敗したら一旦そのまま
      return s
    }
  }

  // relative path の場合 "/dashboard?x=y" -> "/#/dashboard?x=y"
  if (s.startsWith('/')) return `/#${s}`

  // 最後の保険
  return `/#/${s.replace(/^\/+/, '')}`
}

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const rawUrl = (event.notification as any)?.data?.url || '/dashboard?tab=today'
  const normalized = normalizeToHashUrl(rawUrl)
  const url = new URL(normalized, self.registration.scope).toString()

  event.waitUntil(
    (async () => {
      try {
        const payload = {
          type: 'opened',
          notification_id: (event.notification as any)?.data?.notification_id ?? null,
          run_id: (event.notification as any)?.data?.run_id ?? null,
          event_token: (event.notification as any)?.data?.event_token ?? null,
        }

        // ✅ backendへ直接送る（フロントscope依存を排除）
        // - VITE_API_BASE_URL があればそれを使う（例: https://unipa-reminder-backend.onrender.com）
        // - 無ければ本番デフォルトにフォールバック（client.ts と揃える）
        const rawApi =
          ((self as any).__VITE_API_BASE_URL as string | undefined) ||
          'https://unipa-reminder-backend.onrender.com'

        const apiBase = String(rawApi).replace(/\/+$/, '')
        const eventsUrl = `${apiBase}/api/v1/notifications/webpush/events`

        await fetch(eventsUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          // ✅ cookieに依存しない（iOS/Androidの運用耐性）
          credentials: 'omit',
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
