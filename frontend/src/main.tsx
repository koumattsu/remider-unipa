// frontend/src/main.tsx

import React from 'react'
import ReactDOM from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import App from './App.tsx'
import './app.css'; // ← 追加（App全体の外装）
import { registerSW } from 'virtual:pwa-register'

const updateSW = registerSW({
  immediate: false, // 初回ロードでは制御させない
  onNeedRefresh() {
    // 新しいSWが来たら自動リロード
    updateSW(true)
  },
  onOfflineReady() {
    console.log('PWA ready')
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <HashRouter>
      <App />
    </HashRouter>
  </React.StrictMode>,
)