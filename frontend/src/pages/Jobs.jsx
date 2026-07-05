import { useEffect, useState, useCallback, useRef } from 'react';
import { api } from '../services/api';
import { StatusBadge, JobTypeBadge, PriorityBadge } from '../components/Badges';
import { Search, Filter, RefreshCw, Eye, RotateCcw, X, ChevronLeft, ChevronRight } from 'lucide-react';
import { format } from 'date-fns';

const STATUS_OPTIONS = ['', 'pending', 'running', 'completed', 'failed', 'scheduled', 'dead_letter', 'cancelled'];
const TYPE_OPTIONS = ['', 'immediate', 'delayed', 'scheduled', 'recurring', 'batch'];

function JobDetailDrawer({ job, onClose, onRetry }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    api.getJob(job.id).then(setDetail).finally(() => setLoading(false));
  }, [job.id]);

  return (
    <div style={{
      position: 'fixed', right: 0, top: 0, bottom: 0, width: 560,
      background: 'var(--bg-800)', borderLeft: '1px solid var(--border-default)',
      zIndex: 200, display: 'flex', flexDirection: 'column', boxShadow: '-8px 0 40px rgba(0,0,0,0.5)',
      animation: 'slideInRight 200ms ease',
    }}>
      {/* Header */}
      <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700 }}>{detail?.name || `Job ${job.id.slice(0, 8)}...`}</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>{job.id}</div>
        </div>
        <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={18} /></button>
      </div>

      {/* Tabs */}
      <div style={{ padding: '12px 24px', borderBottom: '1px solid var(--border-subtle)' }}>
        <div className="tabs">
          {['overview', 'payload', 'executions', 'logs'].map(t => (
            <button key={t} className={`tab ${activeTab === t ? 'active' : ''}`} onClick={() => setActiveTab(t)}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: 'auto', padding: 24 }}>
        {loading ? <div className="loading-overlay"><div className="spinner" /></div> : (
          <>
            {activeTab === 'overview' && (
              <div className="flex flex-col gap-4">
                <div className="flex gap-2 mb-2">
                  <StatusBadge status={detail?.status} />
                  <JobTypeBadge type={detail?.job_type} />
                  <PriorityBadge priority={detail?.priority} />
                </div>
                {[
                  ['Handler', detail?.handler],
                  ['Attempts', `${detail?.attempt_count} / ${detail?.max_attempts}`],
                  ['Timeout', `${detail?.timeout_seconds}s`],
                  ['Created', detail?.created_at && format(new Date(detail.created_at), 'MMM d, yyyy HH:mm:ss')],
                  ['Started', detail?.started_at && format(new Date(detail.started_at), 'MMM d, yyyy HH:mm:ss')],
                  ['Completed', detail?.completed_at && format(new Date(detail.completed_at), 'MMM d, yyyy HH:mm:ss')],
                  ['Cron', detail?.cron_expression],
                  ['Idempotency Key', detail?.idempotency_key],
                  ['Tags', detail?.tags?.join(', ')],
                ].filter(([, v]) => v).map(([label, value]) => (
                  <div key={label} className="flex justify-between" style={{ padding: '10px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                    <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{label}</span>
                    <span style={{ fontSize: 13, fontFamily: typeof value === 'string' && value.length > 20 ? 'var(--font-mono)' : 'inherit' }}>{value}</span>
                  </div>
                ))}
                {detail?.error_message && (
                  <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, padding: 12, marginTop: 8 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--danger-400)', marginBottom: 4 }}>ERROR</div>
                    <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--danger-400)', whiteSpace: 'pre-wrap' }}>{detail.error_message}</div>
                  </div>
                )}
                {['failed', 'dead_letter', 'cancelled'].includes(detail?.status) && (
                  <button className="btn btn-primary mt-4" onClick={() => onRetry(detail)}>
                    <RotateCcw size={14} /> Retry Job
                  </button>
                )}
              </div>
            )}
            {activeTab === 'payload' && (
              <div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>Job Payload</div>
                <div className="code-block">{JSON.stringify(detail?.payload, null, 2)}</div>
                {detail?.result && (
                  <>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', margin: '16px 0 8px' }}>Result</div>
                    <div className="code-block">{JSON.stringify(detail.result, null, 2)}</div>
                  </>
                )}
              </div>
            )}
            {activeTab === 'executions' && (
              <div className="flex flex-col gap-3">
                {detail?.executions?.length > 0 ? detail.executions.map(ex => (
                  <div key={ex.id} style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 14 }}>
                    <div className="flex justify-between items-center mb-2">
                      <span style={{ fontWeight: 600 }}>Attempt #{ex.attempt_number}</span>
                      <StatusBadge status={ex.status} />
                    </div>
                    {ex.started_at && <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Started: {format(new Date(ex.started_at), 'HH:mm:ss')}</div>}
                    {ex.duration_ms && <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Duration: {ex.duration_ms}ms</div>}
                    {ex.error_message && <div style={{ fontSize: 12, color: 'var(--danger-400)', marginTop: 6, fontFamily: 'var(--font-mono)' }}>{ex.error_message}</div>}
                  </div>
                )) : <div className="empty-state"><p>No executions yet</p></div>}
              </div>
            )}
            {activeTab === 'logs' && (
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                {detail?.logs?.length > 0 ? detail.logs.map(log => (
                  <div key={log.id} className={`log-${log.level}`} style={{ padding: '4px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                    <span style={{ color: 'var(--text-muted)', marginRight: 8 }}>{format(new Date(log.logged_at), 'HH:mm:ss')}</span>
                    <span style={{ marginRight: 8, textTransform: 'uppercase', fontSize: 10 }}>[{log.level}]</span>
                    {log.message}
                  </div>
                )) : <div className="empty-state"><p>No logs</p></div>}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default function Jobs({ wsEvents }) {
  const [orgs, setOrgs] = useState([]);
  const [projects, setProjects] = useState([]);
  const [queues, setQueues] = useState([]);
  const [selectedOrg, setSelectedOrg] = useState('');
  const [selectedProject, setSelectedProject] = useState('');
  const [selectedQueue, setSelectedQueue] = useState('');
  const [jobs, setJobs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ status: '', job_type: '' });
  const [selectedJob, setSelectedJob] = useState(null);
  const [toast, setToast] = useState(null);

  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000); };

  useEffect(() => { api.listOrgs().then(setOrgs).catch(console.error); }, []);
  useEffect(() => {
    if (selectedOrg) api.listProjects(selectedOrg).then(setProjects).catch(console.error);
    else setProjects([]);
    setSelectedProject(''); setSelectedQueue('');
  }, [selectedOrg]);
  useEffect(() => {
    if (selectedProject) api.listQueues(selectedProject).then(setQueues).catch(console.error);
    else setQueues([]);
    setSelectedQueue('');
  }, [selectedProject]);

  const loadJobs = useCallback(async () => {
    if (!selectedQueue) { setJobs([]); return; }
    setLoading(true);
    try {
      const params = { page, page_size: 20, ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) };
      const res = await api.listJobs(selectedQueue, params);
      setJobs(res.items || []);
      setTotal(res.total || 0);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [selectedQueue, page, filters]);

  useEffect(() => { loadJobs(); }, [loadJobs]);

  useEffect(() => {
    if (!wsEvents || !selectedQueue) return;
    const relevant = ['job.created', 'job.completed', 'job.failed', 'job.retried', 'job.cancelled'];
    if (relevant.includes(wsEvents.event)) loadJobs();
  }, [wsEvents, loadJobs, selectedQueue]);

  const handleRetry = async (job) => {
    try {
      await api.retryJob(job.id);
      showToast('Job re-queued for retry');
      loadJobs();
      setSelectedJob(null);
    } catch (e) { showToast(e.message, 'error'); }
  };

  const handleCancel = async (job) => {
    if (!confirm('Cancel this job?')) return;
    try {
      await api.cancelJob(job.id);
      showToast('Job cancelled');
      loadJobs();
    } catch (e) { showToast(e.message, 'error'); }
  };

  const pages = Math.ceil(total / 20);

  return (
    <div>
      {toast && (
        <div style={{ position: 'fixed', top: 20, right: 20, zIndex: 9999, background: 'var(--bg-600)', border: `1px solid ${toast.type === 'error' ? 'var(--danger-400)' : 'var(--success-400)'}`, borderRadius: 8, padding: '12px 18px', fontSize: 14 }}>
          {toast.msg}
        </div>
      )}

      <div className="page-header">
        <div>
          <h1 className="page-title">Job Explorer</h1>
          <p className="page-subtitle">Browse, filter, and inspect all jobs</p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={loadJobs}><RefreshCw size={14} /> Refresh</button>
      </div>

      {/* Filters */}
      <div className="card mb-6" style={{ padding: '16px 20px' }}>
        <div className="flex gap-3 flex-wrap items-center">
          <select className="form-input" style={{ width: 160 }} value={selectedOrg} onChange={e => setSelectedOrg(e.target.value)}>
            <option value="">Select Org</option>
            {orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
          <select className="form-input" style={{ width: 160 }} value={selectedProject} onChange={e => setSelectedProject(e.target.value)} disabled={!selectedOrg}>
            <option value="">Select Project</option>
            {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <select className="form-input" style={{ width: 180 }} value={selectedQueue} onChange={e => setSelectedQueue(e.target.value)} disabled={!selectedProject}>
            <option value="">Select Queue</option>
            {queues.map(q => <option key={q.id} value={q.id}>{q.name}</option>)}
          </select>
          <div style={{ width: 1, height: 28, background: 'var(--border-default)' }} />
          <select className="form-input" style={{ width: 130 }} value={filters.status} onChange={e => setFilters(f => ({ ...f, status: e.target.value }))}>
            {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s || 'All Status'}</option>)}
          </select>
          <select className="form-input" style={{ width: 130 }} value={filters.job_type} onChange={e => setFilters(f => ({ ...f, job_type: e.target.value }))}>
            {TYPE_OPTIONS.map(t => <option key={t} value={t}>{t || 'All Types'}</option>)}
          </select>
        </div>
      </div>

      {/* Jobs Table */}
      {!selectedQueue ? (
        <div className="empty-state card">
          <Filter size={48} style={{ opacity: 0.3 }} />
          <h3>Select a queue to explore jobs</h3>
          <p>Choose an organization, project, and queue from the filters above.</p>
        </div>
      ) : loading ? (
        <div className="loading-overlay"><div className="spinner" /><span>Loading jobs...</span></div>
      ) : jobs.length === 0 ? (
        <div className="empty-state card">
          <h3>No jobs found</h3>
          <p>This queue is empty or no jobs match the current filters.</p>
        </div>
      ) : (
        <>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 12 }}>
            {total.toLocaleString()} jobs total
          </div>
          <div className="table-wrapper mb-4">
            <table>
              <thead>
                <tr>
                  <th>Name / ID</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Priority</th>
                  <th>Attempts</th>
                  <th>Handler</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map(job => (
                  <tr key={job.id}>
                    <td>
                      <div style={{ fontWeight: 600 }}>{job.name || '—'}</div>
                      <div className="mono text-muted" style={{ fontSize: 10 }}>{job.id.slice(0, 16)}...</div>
                    </td>
                    <td><JobTypeBadge type={job.job_type} /></td>
                    <td><StatusBadge status={job.status} /></td>
                    <td><PriorityBadge priority={job.priority} /></td>
                    <td style={{ color: 'var(--text-secondary)' }}>{job.attempt_count}/{job.max_attempts}</td>
                    <td className="mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>{job.handler}</td>
                    <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                      {format(new Date(job.created_at), 'MMM d HH:mm')}
                    </td>
                    <td>
                      <div className="flex gap-1">
                        <button className="btn btn-ghost btn-icon" title="View details" onClick={() => setSelectedJob(job)}>
                          <Eye size={14} />
                        </button>
                        {['failed', 'dead_letter', 'cancelled'].includes(job.status) && (
                          <button className="btn btn-ghost btn-icon" title="Retry" onClick={() => handleRetry(job)}>
                            <RotateCcw size={14} />
                          </button>
                        )}
                        {['pending', 'scheduled'].includes(job.status) && (
                          <button className="btn btn-ghost btn-icon" title="Cancel" onClick={() => handleCancel(job)} style={{ color: 'var(--danger-400)' }}>
                            <X size={14} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {pages > 1 && (
            <div className="flex items-center gap-2 justify-center">
              <button className="btn btn-secondary btn-sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>
                <ChevronLeft size={14} />
              </button>
              <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Page {page} of {pages}</span>
              <button className="btn btn-secondary btn-sm" disabled={page === pages} onClick={() => setPage(p => p + 1)}>
                <ChevronRight size={14} />
              </button>
            </div>
          )}
        </>
      )}

      {/* Job Detail Drawer */}
      {selectedJob && (
        <>
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 199 }} onClick={() => setSelectedJob(null)} />
          <JobDetailDrawer job={selectedJob} onClose={() => setSelectedJob(null)} onRetry={handleRetry} />
        </>
      )}
    </div>
  );
}
