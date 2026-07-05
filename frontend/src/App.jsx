import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useState, useCallback } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { useWebSocket } from './hooks/useWebSocket';
import { ToastContainer, useToast } from './components/Toast';
import Sidebar from './components/Sidebar';
import Login from './pages/Login';
import Overview from './pages/Overview';
import Queues from './pages/Queues';
import Jobs from './pages/Jobs';
import Workers from './pages/Workers';
import DeadLetter from './pages/DeadLetter';
import Settings from './pages/Settings';
import Metrics from './pages/Metrics';
import './index.css';

function ProtectedLayout() {
  const { user, loading } = useAuth();
  const [lastWsEvent, setLastWsEvent] = useState(null);
  const { toasts, toast, removeToast } = useToast();

  const handleWsMessage = useCallback((msg) => {
    setLastWsEvent(msg);
    // Show toast for important events
    const eventMessages = {
      'job.dead_letter': ['Job moved to DLQ', 'error'],
      'job.completed': ['Job completed', 'success'],
      'job.recovered': ['Job recovered from stale worker', 'info'],
    };
    if (eventMessages[msg.event]) {
      const [message, type] = eventMessages[msg.event];
      toast(message, type);
    }
  }, [toast]);

  const wsConnected = useWebSocket(handleWsMessage);

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-900)' }}>
        <div className="spinner" style={{ width: 32, height: 32 }} />
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;

  return (
    <div className="app-layout">
      <Sidebar wsConnected={wsConnected} />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Overview wsEvents={lastWsEvent} />} />
          <Route path="/queues" element={<Queues wsEvents={lastWsEvent} />} />
          <Route path="/jobs" element={<Jobs wsEvents={lastWsEvent} />} />
          <Route path="/workers" element={<Workers wsEvents={lastWsEvent} />} />
          <Route path="/dlq" element={<DeadLetter wsEvents={lastWsEvent} />} />
          <Route path="/metrics" element={<Metrics wsEvents={lastWsEvent} />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
          <Route path="/*" element={<ProtectedLayout />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

function PublicRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/" replace />;
  return children;
}
