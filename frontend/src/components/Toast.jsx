import { useState, useCallback } from 'react';
import { createPortal } from 'react-dom';

let toastId = 0;

function Toast({ toast, onRemove }) {
  const icons = { success: '✓', error: '✕', info: 'ℹ' };
  const colors = { success: 'var(--success-400)', error: 'var(--danger-400)', info: 'var(--primary-400)' };

  return (
    <div className={`toast toast-${toast.type}`} style={{ borderLeft: `3px solid ${colors[toast.type]}` }}>
      <span style={{ color: colors[toast.type], fontWeight: 700 }}>{icons[toast.type]}</span>
      <span style={{ flex: 1 }}>{toast.message}</span>
      <button onClick={() => onRemove(toast.id)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 16 }}>×</button>
    </div>
  );
}

export function ToastContainer({ toasts, removeToast }) {
  if (!toasts.length) return null;
  return createPortal(
    <div className="toast-container">
      {toasts.map(t => <Toast key={t.id} toast={t} onRemove={removeToast} />)}
    </div>,
    document.body
  );
}

export function useToast() {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = 'info', duration = 4000) => {
    const id = ++toastId;
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), duration);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  return { toasts, toast: addToast, removeToast };
}
