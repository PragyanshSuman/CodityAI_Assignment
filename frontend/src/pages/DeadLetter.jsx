import { useEffect, useState, useCallback } from 'react';
import { api } from '../services/api';
import { StatusBadge } from '../components/Badges';
import { AlertTriangle, RotateCcw, Trash2, RefreshCw } from 'lucide-react';
import { format } from 'date-fns';

export default function DeadLetterQueue({ wsEvents }) {
  const [orgs, setOrgs] = useState([]);
  const [projects, setProjects] = useState([]);
  const [queues, setQueues] = useState([]);
  const [selectedOrg, setSelectedOrg] = useState('');
  const [selectedProject, setSelectedProject] = useState('');
  const [selectedQueue, setSelectedQueue] = useState('');
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);

  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000); };

  useEffect(() => { api.listOrgs().then(setOrgs); }, []);
  useEffect(() => {
    if (selectedOrg) api.listProjects(selectedOrg).then(setProjects);
    else setProjects([]); setSelectedProject(''); setSelectedQueue('');
  }, [selectedOrg]);
  useEffect(() => {
    if (selectedProject) api.listQueues(selectedProject).then(setQueues);
    else setQueues([]); setSelectedQueue('');
  }, [selectedProject]);

  const loadDLQ = useCallback(async () => {
    if (!selectedQueue) { setEntries([]); return; }
    setLoading(true);
    try { setEntries(await api.getDLQ(selectedQueue)); }
    catch (e) { console.error(e); } finally { setLoading(false); }
  }, [selectedQueue]);

  useEffect(() => { loadDLQ(); }, [loadDLQ]);
  useEffect(() => {
    if (!wsEvents) return;
    if (['job.dead_letter', 'job.retried'].includes(wsEvents.event)) loadDLQ();
  }, [wsEvents, loadDLQ]);

  const handleRetry = async (entry) => {
    try { await api.retryDLQ(entry.id); showToast('Job re-queued'); loadDLQ(); }
    catch (e) { showToast(e.message, 'error'); }
  };

  const handleDiscard = async (entry) => {
    if (!confirm('Permanently discard this job?')) return;
    try { await api.discardDLQ(entry.id); showToast('Job discarded'); loadDLQ(); }
    catch (e) { showToast(e.message, 'error'); }
  };

  return (
    <div>
      {toast && <div style={{ position: 'fixed', top: 20, right: 20, zIndex: 9999, background: 'var(--bg-600)', border: `1px solid ${toast.type === 'error' ? 'var(--danger-400)' : 'var(--success-400)'}`, borderRadius: 8, padding: '12px 18px', fontSize: 14 }}>{toast.msg}</div>}
      <div className="page-header">
        <div>
          <h1 className="page-title">Dead Letter Queue</h1>
          <p className="page-subtitle">Jobs that permanently failed after exhausting all retries</p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={loadDLQ}><RefreshCw size={14} /></button>
      </div>

      <div className="card mb-6" style={{ padding: '16px 20px' }}>
        <div className="flex gap-3">
          <select className="form-input" style={{ width: 180 }} value={selectedOrg} onChange={e => setSelectedOrg(e.target.value)}>
            <option value="">Select Org</option>
            {orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
          <select className="form-input" style={{ width: 180 }} value={selectedProject} onChange={e => setSelectedProject(e.target.value)} disabled={!selectedOrg}>
            <option value="">Select Project</option>
            {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <select className="form-input" style={{ width: 200 }} value={selectedQueue} onChange={e => setSelectedQueue(e.target.value)} disabled={!selectedProject}>
            <option value="">Select Queue</option>
            {queues.map(q => <option key={q.id} value={q.id}>{q.name}</option>)}
          </select>
        </div>
      </div>

      {!selectedQueue ? (
        <div className="empty-state card">
          <AlertTriangle size={48} style={{ opacity: 0.3 }} />
          <h3>Select a queue to view DLQ</h3>
        </div>
      ) : loading ? (
        <div className="loading-overlay"><div className="spinner" /></div>
      ) : entries.length === 0 ? (
        <div className="empty-state card">
          <AlertTriangle size={48} style={{ opacity: 0.3, color: 'var(--success-400)' }} />
          <h3 style={{ color: 'var(--success-400)' }}>Dead Letter Queue is empty</h3>
          <p>Great — all jobs are either running or have been resolved.</p>
        </div>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Job ID</th>
                <th>Attempts</th>
                <th>Final Error</th>
                <th>AI Summary</th>
                <th>Moved At</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {entries.map(entry => (
                <tr key={entry.id}>
                  <td className="mono" style={{ fontSize: 12 }}>{entry.job_id.slice(0, 16)}...</td>
                  <td><span style={{ color: 'var(--danger-400)', fontWeight: 700 }}>{entry.total_attempts}</span></td>
                  <td style={{ maxWidth: 280 }}>
                    <div style={{ fontSize: 12, color: 'var(--danger-400)', fontFamily: 'var(--font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {entry.final_error || '—'}
                    </div>
                  </td>
                  <td style={{ maxWidth: 200, fontSize: 12, color: 'var(--text-secondary)' }}>
                    {entry.ai_failure_summary || <span style={{ color: 'var(--text-muted)' }}>—</span>}
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{format(new Date(entry.moved_at), 'MMM d HH:mm')}</td>
                  <td>
                    <div className="flex gap-1">
                      <button className="btn btn-secondary btn-sm" onClick={() => handleRetry(entry)} title="Retry">
                        <RotateCcw size={13} /> Retry
                      </button>
                      <button className="btn btn-danger btn-sm" onClick={() => handleDiscard(entry)} title="Discard">
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
