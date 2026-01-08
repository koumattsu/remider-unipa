// frontend/src/sw.ts
/// <reference lib="webworker" />

// 何もしない最小SW（ビルド通す用）
self.addEventListener('install', () => {
  // 即時有効化したいならコメント外す
  // self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  // すぐクライアントを制御したいならコメント外す
  // event.waitUntil(self.clients.claim());
});
