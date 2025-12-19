// frontend/src/App.tsx

import { Routes, Route, Navigate } from 'react-router-dom';
import { Login } from './pages/Login';
import { AuthCallback } from './pages/AuthCallback';
import { Dashboard } from './pages/Dashboard';

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<Login />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

export default App;
