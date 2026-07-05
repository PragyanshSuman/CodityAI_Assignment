import { useEffect, useState, useCallback } from 'react';
import { api } from '../services/api';
import { StatusBadge } from '../components/Badges';
import { Plus, Pause, Play, Trash2, Settings, BarChart2, RefreshCw, X } from 'lucide-react';
import { format } from 'date-fns';

function CreateQueueModal({ projectId, onClose, onCreated }) {
  const [form, setForm] = useState({ name: '', slug: '', description: '', priority: 5, concurrency_limit: 10, rate_limit_per_minute: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const payload = { ...form, rate_limit_per_minute: form.rate_limit_per_minute ? Number(form.rate_limit_per_minute) : null };
      const q = await api.createQueue(projectId, payload);
      onCreated(q);
      onClose();
    } catch (err) { setError(err.message); } finally { setLoading(false); }
  };

  return (
    <div className="modal-overlay">
      <div className="modal">
        <div className="modal-header">
          <h2 className="modal-title">Create Queue</h2>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={18} /></button>
        </div>
        {error && <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: 'var(--danger-400)', marginBottom: 16 }}>{error}</div>}
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="form-group">
            <label className="form-label">Queue Name *</label>
            <input className="form-input" value={form.name} onChange={e => { setForm(f => ({ ...f, name: e.target.value, slug: e.target.value.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '') })); }} required />
          </div>
          <div className="form-group">
            <label className="form-label">Slug *</label>
            <input className="form-input" value={form.slug} onChange={e => setForm(f => ({ ...f, slug: e.target.value }))} required pattern="[a-z0-9-]+" />
          </div>
          <div className="form-group">
            <label className="form-label">Description</label>
            <textarea className="form-input" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} style={{ minHeight: 60 }} />
          </div>
          <div className="grid-2" style={{ gap: 12 }}>
            <div className="form-group">
              <label className="form-label">Priority (1-10)</label>
              <input className="form-input" type="number" min={1} max={10} value={form.priority} onChange={e => setForm(f => ({ ...f, priority: Number(e.target.value) }))} />
            </div>
            <div className="form-group">
              <label className="form-label">Concurrency Limit</label>
              <input className="form-input" type="number" min={1} value={form.concurrency_limit} onChange={e => setForm(f => ({ ...f, concurrency_limit: Number(e.target.value) }))} />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Rate Limit (jobs/min, optional)</label>
            <input className="form-input" type="number" min={1} value={form.rate_limit_per_minute} onChange={e => setForm(f => ({ ...f, rate_limit_per_minute: e.target.value }))} placeholder="Unlimited" />
          </div>
          <div className="flex gap-3 mt-2">
            <button type="button" className="btn btn-secondary flex-1" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary flex-1" disabled={loading}>{loading ? 'Creating...' : 'Create Queue'}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

function CreateJobModal({ queue, onClose, onCreated }) {
  const [form, setForm] = useState({ name: '', job_type: 'immediate', handler: 'default', payload: '{}', priority: 5, max_attempts: 3, timeout_seconds: 300, scheduled_at: '', cron_expression: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault(); setLoading(true); setError('');
    try {
      let payload;
      try { payload = JSON.parse(form.payload); } catch { setError('Payload must be valid JSON'); setLoading(false); return; }
      const data = {
        name: form.name || undefined, job_type: form.job_type, handler: form.handler,
        payload, priority: form.priority, max_attempts: form.max_attempts, timeout_seconds: form.timeout_seconds,
        scheduled_at: form.scheduled_at || undefined, cron_expression: form.cron_expression || undefined,
      };
      const job = await api.createJob(queue.id, data);
      onCreated(job); onClose();
    } catch (err) { setError(err.message); } finally { setLoading(false); }
  };

  return (
    <div className="modal-overlay">
      <div className="modal" style={{ maxWidth: 600 }}>
        <div className="modal-header">
          <h2 className="modal-title">Submit Job</h2>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={18} /></button>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>Queue: <strong style={{ color: 'var(--primary-400)' }}>{queue.name}</strong></div>
        {error && <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: 'var(--danger-400)', marginBottom: 16 }}>{error}</div>}
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="grid-2" style={{ gap: 12 }}>
            <div className="form-group">
              <label className="form-label">Job Name (optional)</label>
              <input className="form-input" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. Send Welcome Email" />
            </div>
            <div className="form-group">
              <label className="form-label">Job Type *</label>
              <select className="form-input" value={form.job_type} onChange={e => setForm(f => ({ ...f, job_type: e.target.value }))}>
                <option value="immediate">Immediate</option>
                <option value="delayed">Delayed</option>
                <option value="scheduled">Scheduled</option>
                <option value="recurring">Recurring (Cron)</option>
              </select>
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Handler *</label>
            <select className="form-input" value={form.handler} onChange={e => setForm(f => ({ ...f, handler: e.target.value }))}>
              <option value="default">default</option>
              <option value="email.send_welcome">email.send_welcome</option>
              <option value="report.generate">report.generate</option>
            </select>
          </div>
          {['delayed', 'scheduled'].includes(form.job_type) && (
            <div className="form-group">
              <label className="form-label">Scheduled At *</label>
              <input className="form-input" type="datetime-local" value={form.scheduled_at} onChange={e => setForm(f => ({ ...f, scheduled_at: e.target.value }))} />
            </div>
          )}
          {form.job_type === 'recurring' && (
            <div className="form-group">
              <label className="form-label">Cron Expression *</label>
              <input className="form-input" value={form.cron_expression} onChange={e => setForm(f => ({ ...f, cron_expression: e.target.value }))} placeholder="*/5 * * * *" />
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Standard 5-field cron (minute hour day month weekday)</span>
            </div>
          )}
          <div className="form-group">
            <label className="form-label">Payload (JSON)</label>
            <textarea className="form-input" value={form.payload} onChange={e => setForm(f => ({ ...f, payload: e.target.value }))} style={{ minHeight: 100 }} />
          </div>
          <div className="grid-2" style={{ gap: 12 }}>
            <div className="form-group">
              <label className="form-label">Priority</label>
              <input className="form-input" type="number" min={1} max={10} value={form.priority} onChange={e => setForm(f => ({ ...f, priority: Number(e.target.value) }))} />
            </div>
            <div className="form-group">
              <label className="form-label">Max Attempts</label>
              <input className="form-input" type="number" min={1} max={50} value={form.max_attempts} onChange={e => setForm(f => ({ ...f, max_attempts: Number(e.target.value) }))} />
            </div>
          </div>
          <div className="flex gap-3 mt-2">
            <button type="button" className="btn btn-secondary flex-1" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary flex-1" disabled={loading}>{loading ? 'Submitting...' : 'Submit Job'}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Queues({ wsEvents }) {
  const [orgs, setOrgs] = useState([]);
  const [projects, setProjects] = useState([]);
  const [selectedOrg, setSelectedOrg] = useState('');
  const [selectedProject, setSelectedProject] = useState('');
  const [queues, setQueues] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showCreateQ, setShowCreateQ] = useState(false);
  const [submitQueue, setSubmitQueue] = useState(null);
  const [queueStats, setQueueStats] = useState({});
  const [toast, setToast] = useState(null);

  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000); };

  useEffect(() => { api.listOrgs().then(setOrgs).catch(console.error); }, []);
  useEffect(() => {
    if (selectedOrg) api.listProjects(selectedOrg).then(setProjects).catch(console.error);
    else setProjects([]);
    setSelectedProject('');
  }, [selectedOrg]);

  const loadQueues = useCallback(async () => {
    if (!selectedProject) { setQueues([]); return; }
    setLoading(true);
    try {
      const qs = await api.listQueues(selectedProject);
      setQueues(qs);
      // Load stats for each queue
      const statsMap = {};
      await Promise.all(qs.map(async q => {
        try { statsMap[q.id] = await api.getQueueStats(q.id); } catch {}
      }));
      setQueueStats(statsMap);
    } catch (e) { console.error(e); } finally { setLoading(false); }
  }, [selectedProject]);

  useEffect(() => { loadQueues(); }, [loadQueues]);
  useEffect(() => {
    if (!wsEvents) return;
    if (['queue.created', 'queue.updated', 'queue.paused', 'queue.resumed'].includes(wsEvents.event)) loadQueues();
  }, [wsEvents, loadQueues]);

  const handlePause = async (q) => {
    try {
      await (q.is_paused ? api.resumeQueue(q.id) : api.pauseQueue(q.id));
      showToast(`Queue ${q.is_paused ? 'resumed' : 'paused'}`);
      loadQueues();
    } catch (e) { showToast(e.message, 'error'); }
  };

  const handleDelete = async (q) => {
    if (!confirm(`Delete queue "${q.name}"?`)) return;
    try { await api.deleteQueue(q.id); showToast('Queue deleted'); loadQueues(); }
    catch (e) { showToast(e.message, 'error'); }
  };

  return (
    <div>
      {toast && (
        <div style={{ position: 'fixed', top: 20, right: 20, zIndex: 9999, background: 'var(--bg-600)', border: `1px solid ${toast.type === 'error' ? 'var(--danger-400)' : 'var(--success-400)'}`, borderRadius: 8, padding: '12px 18px', fontSize: 14 }}>
          {toast.msg}
        </div>
      )}
      <div className="page-header">
        <div>
          <h1 className="page-title">Queue Manager</h1>
          <p className="page-subtitle">Configure and monitor your job queues</p>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-secondary btn-sm" onClick={loadQueues}><RefreshCw size={14} /></button>
          {selectedProject && <button className="btn btn-primary btn-sm" onClick={() => setShowCreateQ(true)}><Plus size={14} /> New Queue</button>}
        </div>
      </div>

      {/* Project selector */}
      <div className="card mb-6" style={{ padding: '16px 20px' }}>
        <div className="flex gap-3 items-center">
          <select className="form-input" style={{ width: 200 }} value={selectedOrg} onChange={e => setSelectedOrg(e.target.value)}>
            <option value="">Select Organization</option>
            {orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
          <select className="form-input" style={{ width: 200 }} value={selectedProject} onChange={e => setSelectedProject(e.target.value)} disabled={!selectedOrg}>
            <option value="">Select Project</option>
            {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </div>
      </div>

      {!selectedProject ? (
        <div className="empty-state card"><Settings size={48} style={{ opacity: 0.3 }} /><h3>Select a project</h3><p>Choose an organization and project to manage its queues.</p></div>
      ) : loading ? (
        <div className="loading-overlay"><div className="spinner" /></div>
      ) : queues.length === 0 ? (
        <div className="empty-state card"><h3>No queues yet</h3><p>Create a queue to start scheduling jobs.</p><button className="btn btn-primary mt-4" onClick={() => setShowCreateQ(true)}><Plus size={14} /> Create Queue</button></div>
      ) : (
        <div className="flex flex-col gap-4">
          {queues.map(q => {
            const stats = queueStats[q.id];
            return (
              <div key={q.id} className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-3 mb-1">
                      <span style={{ fontSize: 17, fontWeight: 700 }}>{q.name}</span>
                      <StatusBadge status={q.is_paused ? 'paused' : 'active'} />
                      <span style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{q.slug}</span>
                    </div>
                    {q.description && <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{q.description}</p>}
                    <div className="flex gap-4 mt-2">
                      {[
                        [`Priority: P${q.priority}`, 'var(--primary-400)'],
                        [`Concurrency: ${q.concurrency_limit}`, 'var(--accent-400)'],
                        q.rate_limit_per_minute && [`Rate: ${q.rate_limit_per_minute}/min`, 'var(--warning-400)'],
                      ].filter(Boolean).map(([text, color]) => (
                        <span key={text} style={{ fontSize: 12, color, fontWeight: 600 }}>{text}</span>
                      ))}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button className="btn btn-secondary btn-sm" onClick={() => setSubmitQueue(q)}><Plus size={13} /> Submit Job</button>
                    <button className="btn btn-secondary btn-sm" title={q.is_paused ? 'Resume' : 'Pause'} onClick={() => handlePause(q)}>
                      {q.is_paused ? <Play size={13} /> : <Pause size={13} />}
                      {q.is_paused ? 'Resume' : 'Pause'}
                    </button>
                    <button className="btn btn-danger btn-sm" onClick={() => handleDelete(q)}><Trash2 size={13} /></button>
                  </div>
                </div>

                {/* Stats Bar */}
                {stats && (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, background: 'var(--surface-2)', borderRadius: 8, padding: '12px 16px' }}>
                    {[
                      ['Pending', stats.pending_count, 'var(--warning-400)'],
                      ['Running', stats.running_count, 'var(--accent-400)'],
                      ['Completed', stats.completed_count, 'var(--success-400)'],
                      ['Failed', stats.failed_count, 'var(--danger-400)'],
                      ['DLQ', stats.dead_letter_count, '#fc8585'],
                    ].map(([label, val, color]) => (
                      <div key={label} style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: 22, fontWeight: 800, color }}>{val}</div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{label}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {showCreateQ && <CreateQueueModal projectId={selectedProject} onClose={() => setShowCreateQ(false)} onCreated={q => { setQueues(prev => [q, ...prev]); }} />}
      {submitQueue && <CreateJobModal queue={submitQueue} onClose={() => setSubmitQueue(null)} onCreated={() => showToast('Job submitted!')} />}
    </div>
  );
}
