// frontend/src/main.tsx

import React from 'react'
import ReactDOM from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import App from './App.tsx'
import './app.css'; // ← 追加（App全体の外装）
import { registerSW } from 'virtual:pwa-register'

const updateSW = registerSW({
  // ✅ 初回からSWの登録/更新を進め、世代ズレで起動に失敗する確率を下げる
  immediate: true,
  onNeedRefresh() {
    // ✅ 新しいSWが来たら即適用してリロード（“開かない”より圧倒的に安全）
    updateSW(true)
  },
  onOfflineReady() {
    console.log('PWA ready')
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <HashRouter>
      <div className="app-shell">
        <div className="bg-layer" aria-hidden="true">
          <span className="bg-spot s1" />
          <span className="bg-spot s2" />
          <span className="bg-spot s3" />
        </div>
        <App />
      </div>
    </HashRouter>
  </React.StrictMode>,
)