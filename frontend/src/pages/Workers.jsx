import { useEffect, useState, useCallback } from 'react';
import { api } from '../services/api';
import { StatusBadge } from '../components/Badges';
import { Server, RefreshCw, PowerOff, Activity } from 'lucide-react';
import { format, formatDistanceToNow } from 'date-fns';

export default function Workers({ wsEvents }) {
  const [workers, setWorkers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [heartbeats, setHeartbeats] = useState([]);
  const [toast, setToast] = useState(null);

  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000); };

  const loadWorkers = useCallback(async () => {
    try {
      const ws = await api.listWorkers();
      setWorkers(ws);
    } catch (e) { console.error(e); } finally { setLoading(false); }
  }, []);

  useEffect(() => { loadWorkers(); const t = setInterval(loadWorkers, 5000); return () => clearInterval(t); }, [loadWorkers]);

  const handleSelect = async (w) => {
    setSelected(w);
    const hbs = await api.getWorkerHeartbeats(w.id).catch(() => []);
    setHeartbeats(hbs);
  };

  const handleShutdown = async (w) => {
    if (!confirm(`Gracefully shutdown worker ${w.name || w.id.slice(0, 8)}?`)) return;
    try { await api.shutdownWorker(w.id); showToast('Shutdown initiated'); loadWorkers(); }
    catch (e) { showToast(e.message, 'error'); }
  };

  const active = workers.filter(w => w.is_healthy && w.status !== 'offline');
  const offline = workers.filter(w => !w.is_healthy || w.status === 'offline');

  return (
    <div>
      {toast && <div style={{ position: 'fixed', top: 20, right: 20, zIndex: 9999, background: 'var(--bg-600)', border: `1px solid ${toast.type === 'error' ? 'var(--danger-400)' : 'var(--success-400)'}`, borderRadius: 8, padding: '12px 18px', fontSize: 14 }}>{toast.msg}</div>}
      <div className="page-header">
        <div>
          <h1 className="page-title">Worker Monitor</h1>
          <p className="page-subtitle">{active.length} active · {workers.reduce((s, w) => s + w.current_jobs, 0)} jobs running</p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={loadWorkers}><RefreshCw size={14} /> Refresh</button>
      </div>

      <div className="grid-3 mb-8">
        {[
          ['Active Workers', active.length, 'var(--success-400)'],
          ['Total Jobs Running', workers.reduce((s, w) => s + (w.current_jobs || 0), 0), 'var(--accent-400)'],
          ['Workers Offline', offline.length, 'var(--danger-400)'],
        ].map(([label, value, color]) => (
          <div key={label} className="stat-card">
            <span className="stat-label">{label}</span>
            <span className="stat-value" style={{ color }}>{value}</span>
          </div>
        ))}
      </div>

      {loading ? <div className="loading-overlay"><div className="spinner" /></div> : workers.length === 0 ? (
        <div className="empty-state card">
          <Server size={48} style={{ opacity: 0.3 }} />
          <h3>No workers registered</h3>
          <p>Start the worker process to begin processing jobs.</p>
          <div className="code-block mt-4" style={{ textAlign: 'left', width: '100%', maxWidth: 400 }}>python -m app.worker.main</div>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {workers.map(w => (
            <div key={w.id} className="card" style={{ cursor: 'pointer', borderColor: selected?.id === w.id ? 'var(--primary-500)' : undefined }}
              onClick={() => selected?.id === w.id ? setSelected(null) : handleSelect(w)}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div style={{ width: 40, height: 40, borderRadius: 10, background: w.is_healthy ? 'rgba(34,197,94,0.1)' : 'rgba(100,100,120,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Server size={20} color={w.is_healthy ? 'var(--success-400)' : 'var(--text-muted)'} />
                  </div>
                  <div>
                    <div style={{ fontWeight: 700 }}>{w.name || `worker-${w.id.slice(0, 8)}`}</div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{w.hostname} · PID {w.pid}</div>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--accent-400)' }}>{w.current_jobs}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>/ {w.max_concurrency} jobs</div>
                  </div>
                  <StatusBadge status={w.is_healthy ? w.status : 'offline'} />
                  {w.is_healthy && (
                    <button className="btn btn-danger btn-sm" onClick={e => { e.stopPropagation(); handleShutdown(w); }}>
                      <PowerOff size={13} /> Shutdown
                    </button>
                  )}
                </div>
              </div>

              {/* Utilization Bar */}
              <div style={{ marginTop: 12 }}>
                <div className="flex justify-between mb-1">
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Utilization</span>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{w.last_heartbeat_at && formatDistanceToNow(new Date(w.last_heartbeat_at), { addSuffix: true })}</span>
                </div>
                <div className="progress-bar">
                  <div className="progress-bar-fill" style={{ width: `${Math.min(100, (w.current_jobs / w.max_concurrency) * 100)}%` }} />
                </div>
              </div>

              {/* Heartbeat Detail */}
              {selected?.id === w.id && heartbeats.length > 0 && (
                <div style={{ marginTop: 16, padding: '12px 16px', background: 'var(--surface-2)', borderRadius: 8 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 10 }}>Recent Heartbeats</div>
                  <div className="table-wrapper">
                    <table>
                      <thead><tr><th>Time</th><th>Status</th><th>Jobs</th><th>Memory</th><th>CPU</th></tr></thead>
                      <tbody>
                        {heartbeats.slice(0, 10).map(hb => (
                          <tr key={hb.id}>
                            <td style={{ fontSize: 12 }}>{format(new Date(hb.recorded_at), 'HH:mm:ss')}</td>
                            <td><StatusBadge status={hb.status || 'active'} /></td>
                            <td>{hb.current_jobs ?? '—'}</td>
                            <td>{hb.memory_mb ? `${hb.memory_mb.toFixed(0)}MB` : '—'}</td>
                            <td>{hb.cpu_percent ? `${hb.cpu_percent.toFixed(1)}%` : '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
